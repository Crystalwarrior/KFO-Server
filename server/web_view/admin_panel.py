import asyncio
import json
import logging
import os
import secrets
import ssl
import time

import aiohttp
from aiohttp import web

from server import database

logger = logging.getLogger("admin_panel")

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# In-memory session store: token -> {"user": str, "created": float}
_sessions = {}
_SESSION_TTL = 3600 * 8  # 8 hours

# Rate limiting: ip -> [timestamp, ...] of failed login attempts
_login_attempts = {}
_rate_limit_config = {
    "max_attempts": 5,
    "window_seconds": 300,
    "lockout_seconds": 300,
}

# Cached HTML loaded at startup
_login_html = None
_admin_html = None

# Mock client instances keyed by session token, persists state across commands
_remote_clients = {}

# Active WebSocket connections for OOC/IC forwarding
_ws_clients = set()


def _load_template(name):
    """Load an HTML template from the templates directory."""
    path = os.path.join(_TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _verify_password(stored, password):
    """Verify a plaintext password."""
    return stored == password


def _get_admin_credentials(config):
    """Extract admin panel credentials from config."""
    admin_cfg = config.get("admin_panel", {})
    users = admin_cfg.get("users", {})
    if not users:
        raise ValueError("No admin users configured. Set at least one admin user.")
    return users


def _create_session(user):
    """Create a new session token for a user."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"user": user, "created": time.time()}
    return token


def _validate_session(token):
    """Check if a session token is valid."""
    if token not in _sessions:
        return None
    session = _sessions[token]
    if time.time() - session["created"] > _SESSION_TTL:
        del _sessions[token]
        return None
    return session["user"]


def _cleanup_sessions():
    """Remove expired sessions."""
    now = time.time()
    expired = [t for t, s in _sessions.items() if now - s["created"] > _SESSION_TTL]
    for t in expired:
        del _sessions[t]
        remote = _remote_clients.pop(t, None)
        if remote:
            remote.leave_area()
            remote.clear()
            remote._listeners.clear()


def _require_auth(handler):
    """Decorator that requires a valid session for HTTP handlers."""

    async def wrapper(request):
        token = request.cookies.get("admin_session")
        if not token:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
        user = _validate_session(token) if token else None
        if user is None:
            if request.path.startswith("/api/"):
                return web.json_response({"error": "unauthorized"}, status=401)
            return web.HTTPFound("/login")
        request["admin_user"] = user
        return await handler(request)

    return wrapper


async def handle_login_page(request):
    """Serve the login page."""
    return web.Response(text=_login_html, content_type="text/html")


def _is_rate_limited(ip):
    """Check if an IP is currently rate-limited. Returns remaining lockout seconds or 0."""
    now = time.time()
    max_attempts = _rate_limit_config["max_attempts"]
    window = _rate_limit_config["window_seconds"]
    lockout = _rate_limit_config["lockout_seconds"]

    attempts = _login_attempts.get(ip, [])
    # Prune old attempts outside the window
    attempts = [t for t in attempts if now - t < window]

    # Check if locked out
    if len(attempts) >= max_attempts:
        last_attempt = max(attempts)
        remaining = lockout - (now - last_attempt)
        if remaining > 0:
            _login_attempts[ip] = attempts
            return int(remaining) + 1
        else:
            # Lockout expired, clear attempts
            attempts = []

    _login_attempts[ip] = attempts
    return 0


def _record_failed_login(ip):
    """Record a failed login attempt for an IP."""
    _login_attempts.setdefault(ip, []).append(time.time())


def _clear_login_attempts(ip):
    """Clear failed login attempts for an IP (on successful login)."""
    _login_attempts.pop(ip, None)


async def handle_login(request):
    """Process a login attempt."""
    ip = request.remote

    # Check rate limit
    remaining = _is_rate_limited(ip)
    if remaining > 0:
        return web.json_response(
            {"error": f"Too many failed attempts. Try again in {remaining} seconds."},
            status=429,
        )

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid request"}, status=400)

    username = data.get("username", "")
    password = data.get("password", "")

    credentials = _get_admin_credentials(request.app["config"])
    if username not in credentials:
        _record_failed_login(ip)
        remaining = _is_rate_limited(ip)
        if remaining > 0:
            return web.json_response(
                {"error": f"Too many failed attempts. Try again in {remaining} seconds."},
                status=429,
            )
        return web.json_response({"error": "invalid credentials"}, status=401)

    if not _verify_password(credentials[username], password):
        _record_failed_login(ip)
        remaining = _is_rate_limited(ip)
        if remaining > 0:
            return web.json_response(
                {"error": f"Too many failed attempts. Try again in {remaining} seconds."},
                status=429,
            )
        return web.json_response({"error": "invalid credentials"}, status=401)

    _clear_login_attempts(ip)
    token = _create_session(username)
    response = web.json_response({"ok": True, "user": username})
    response.set_cookie("admin_session", token, httponly=True, samesite="Lax", max_age=_SESSION_TTL)
    return response


async def handle_logout(request):
    """Log out the current user."""
    token = request.cookies.get("admin_session")
    if token and token in _sessions:
        del _sessions[token]
        remote = _remote_clients.pop(token, None)
        if remote:
            remote.leave_area()
            remote.clear()
            remote._listeners.clear()
    response = web.json_response({"ok": True})
    response.del_cookie("admin_session")
    return response


@_require_auth
async def handle_main(request):
    """Serve the main admin panel page."""
    return web.Response(text=_admin_html, content_type="text/html")


@_require_auth
async def handle_api_hubs(request):
    """Get all hubs with areas."""
    db = database._database_singleton
    hubs = db.get_hubs()
    for hub in hubs:
        hub["areas"] = db.get_areas_for_hub(hub["hub_id"])
    return web.json_response(hubs)


@_require_auth
async def handle_api_areas(request):
    """Get areas, optionally filtered by hub."""
    hub_id = request.query.get("hub_id")
    if hub_id is not None:
        hub_id = int(hub_id)
    db = database._database_singleton
    areas = db.get_areas_for_hub(hub_id)
    return web.json_response(areas)


@_require_auth
async def handle_api_event_types(request):
    """Get event type names."""
    category = request.query.get("category", "area")
    db = database._database_singleton
    types = db.get_event_types(category)
    return web.json_response(types)


@_require_auth
async def handle_api_area_events(request):
    """Query area events."""
    db = database._database_singleton
    params = {}
    for key in ("hub_id", "area_id", "event_subtype", "ipid", "since", "until", "limit", "offset"):
        val = request.query.get(key)
        if val is not None:
            if key in ("hub_id", "area_id", "ipid", "limit", "offset"):
                val = int(val)
            params[key] = val
    params.setdefault("limit", 100)
    params.setdefault("offset", 0)

    events = db.query_area_events(**params)
    total = db.count_area_events(
        hub_id=params.get("hub_id"),
        area_id=params.get("area_id"),
        event_subtype=params.get("event_subtype"),
        ipid=params.get("ipid"),
        since=params.get("since"),
        until=params.get("until"),
    )
    return web.json_response({"events": events, "total": total})


@_require_auth
async def handle_api_connect_events(request):
    """Query connect events."""
    db = database._database_singleton
    params = {}
    for key in ("ipid", "since", "until", "limit", "offset"):
        val = request.query.get(key)
        if val is not None:
            if key in ("ipid", "limit", "offset"):
                val = int(val)
            params[key] = val
    failed = request.query.get("failed")
    if failed is not None:
        params["failed"] = failed.lower() in ("true", "1", "yes")
    params.setdefault("limit", 100)
    params.setdefault("offset", 0)

    events = db.query_connect_events(**params)
    total = db.count_connect_events(
        ipid=params.get("ipid"),
        failed=params.get("failed"),
        since=params.get("since"),
        until=params.get("until"),
    )
    return web.json_response({"events": events, "total": total})


@_require_auth
async def handle_api_misc_events(request):
    """Query misc events."""
    db = database._database_singleton
    params = {}
    for key in ("event_subtype", "ipid", "since", "until", "limit", "offset"):
        val = request.query.get(key)
        if val is not None:
            if key in ("ipid", "limit", "offset"):
                val = int(val)
            params[key] = val
    params.setdefault("limit", 100)
    params.setdefault("offset", 0)

    events = db.query_misc_events(**params)
    total = db.count_misc_events(
        event_subtype=params.get("event_subtype"),
        ipid=params.get("ipid"),
        since=params.get("since"),
        until=params.get("until"),
    )
    return web.json_response({"events": events, "total": total})


def _ws_forward(entry):
    """Send an OOC/IC event entry to all connected admin WebSocket clients."""
    loop = asyncio.get_event_loop()
    for ws in list(_ws_clients):
        if ws.closed:
            _ws_clients.discard(ws)
            continue
        loop.call_soon(asyncio.ensure_future, ws.send_json(entry))


@_require_auth
async def handle_api_ooc_monitor(request):
    """Enable or disable OOC+IC monitoring. When enabled, the remote client
    joins the area as a real participant and intercepts CT/MS packets."""
    server = request.app["server"]
    if server is None:
        return web.json_response({"error": "server not available"}, status=503)

    data = await request.json()
    token = request.cookies.get("admin_session", "")
    enable = data.get("enable", False)

    if token not in _remote_clients:
        from server.remote_client import RemoteClient

        _remote_clients[token] = RemoteClient(server, is_mod=True, name="[ADMIN]")
    remote = _remote_clients[token]

    if enable:
        # Join area if not already in one
        if not remote._in_area:
            remote.join_area()
        # Register listener for forwarding to WebSocket
        remote.remove_listener(_ws_forward)
        remote.add_listener(_ws_forward)
        return web.json_response(
            {
                "ok": True,
                "monitoring": True,
                "area_id": remote.area.id if remote.area else -1,
                "area_name": remote.area.name if remote.area else "?",
            }
        )
    else:
        remote.remove_listener(_ws_forward)
        remote.leave_area()
        return web.json_response({"ok": True, "monitoring": False})


@_require_auth
async def handle_api_ic_monitor(request):
    """Enable or disable IC monitoring (same as OOC — both are captured)."""
    # IC monitoring is handled by the same mechanism as OOC.
    # The remote client intercepts both CT and MS when in the area.
    return await handle_api_ooc_monitor(request)


@_require_auth
async def handle_api_players(request):
    """List all connected players."""
    server = request.app["server"]
    if server is None:
        return web.json_response({"error": "server not available"}, status=503)

    players = []
    for client in server.client_manager.clients:
        players.append(
            {
                "id": client.id,
                "name": client.name,
                "char_name": getattr(client, "char_name", ""),
                "showname": getattr(client, "showname", ""),
                "ipid": client.ipid,
                "area_id": client.area.id if client.area else -1,
                "area_name": client.area.name if client.area else "Unknown",
                "is_mod": client.is_mod,
                "is_muted": client.is_muted,
                "is_ooc_muted": client.is_ooc_muted,
            }
        )
    return web.json_response(players)


@_require_auth
async def handle_api_command(request):
    """Execute a server command as the system admin."""
    server = request.app["server"]
    if server is None:
        return web.json_response({"error": "server not available"}, status=503)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid request"}, status=400)

    cmd = data.get("cmd", "").strip()
    arg = data.get("arg", "")

    if not cmd:
        return web.json_response({"error": "no command specified"}, status=400)

    token = request.cookies.get("admin_session", "")

    # Reuse the same remote client per session so state (area, etc.) persists
    if token not in _remote_clients:
        from server.remote_client import RemoteClient

        _remote_clients[token] = RemoteClient(server, is_mod=True, name="[ADMIN]")
    remote = _remote_clients[token]

    # Ensure the remote client is in the area before executing commands
    if not remote._in_area:
        remote.join_area()

    if cmd == "ooc":
        if not remote.area:
            return web.json_response({"error": "no area context"}, status=400)
        if not arg:
            return web.json_response({"error": "usage: /ooc <message>"}, status=400)
        # Build name like net_cmd_ct does
        prefix = "[M]" if remote.is_mod else ""
        name = f"{prefix}{remote.name}"
        # Send through area.send_command — remote client receives it naturally
        remote.area.send_command("CT", name, arg)
        return web.json_response(
            {
                "output": [f"OOC: {arg}"],
                "cmd": cmd,
                "arg": arg,
            }
        )

    output = remote.execute(cmd, arg)
    return web.json_response(
        {
            "output": output,
            "cmd": cmd,
            "arg": arg,
        }
    )


@_require_auth
async def handle_ws_live(request):
    """WebSocket endpoint for live log streaming."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    db = database._database_singleton
    queue = db.subscribe()
    _ws_clients.add(ws)
    logger.info("Admin %s connected to live log stream", request["admin_user"])

    try:
        await ws.send_json({"type": "connected", "message": "Live log stream connected"})

        async def listen_client():
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get("type") == "ping":
                            await ws.send_json({"type": "pong"})
                    except Exception:
                        pass
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break

        listener = asyncio.ensure_future(listen_client())

        try:
            while not ws.closed:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30)
                    await ws.send_json(entry)
                except asyncio.TimeoutError:
                    await ws.ping()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            listener.cancel()
    finally:
        _ws_clients.discard(ws)
        db.unsubscribe(queue)
        logger.info("Admin %s disconnected from live log stream", request["admin_user"])

    return ws


def create_admin_app(config, server=None):
    """
    Create and configure the aiohttp admin panel application.
    Returns (app, ssl_context) where ssl_context may be None.
    """
    global _login_html, _admin_html

    _login_html = _load_template("login.html")
    _admin_html = _load_template("admin.html")

    # Silence the per-request access log spam
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    # Load rate limit config
    admin_cfg = config.get("admin_panel", {})
    rl = admin_cfg.get("rate_limit", {})
    _rate_limit_config["max_attempts"] = rl.get("max_attempts", 5)
    _rate_limit_config["window_seconds"] = rl.get("window_seconds", 300)
    _rate_limit_config["lockout_seconds"] = rl.get("lockout_seconds", 300)

    app = web.Application()
    app["config"] = config
    app["server"] = server

    # Page routes
    app.router.add_get("/", handle_main)
    app.router.add_get("/login", handle_login_page)

    # Auth routes
    app.router.add_post("/api/login", handle_login)
    app.router.add_post("/api/logout", handle_logout)

    # API routes
    app.router.add_get("/api/hubs", handle_api_hubs)
    app.router.add_get("/api/areas", handle_api_areas)
    app.router.add_get("/api/event_types", handle_api_event_types)
    app.router.add_get("/api/area_events", handle_api_area_events)
    app.router.add_get("/api/connect_events", handle_api_connect_events)
    app.router.add_get("/api/misc_events", handle_api_misc_events)

    # Admin command routes
    app.router.add_get("/api/admin/players", handle_api_players)
    app.router.add_post("/api/admin/command", handle_api_command)
    app.router.add_post("/api/admin/ooc_monitor", handle_api_ooc_monitor)
    app.router.add_post("/api/admin/ic_monitor", handle_api_ic_monitor)

    # WebSocket route
    app.router.add_get("/ws/live", handle_ws_live)

    # Static files (CSS, JS)
    app.router.add_static("/static", _STATIC_DIR)

    # Build SSL context
    ssl_context = None
    ssl_cert = admin_cfg.get("ssl_cert")
    ssl_key = admin_cfg.get("ssl_key")
    domain = admin_cfg.get("domain")

    if ssl_cert and ssl_key:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(ssl_cert, ssl_key)
        logger.info("Admin panel SSL enabled (cert: %s, key: %s)", ssl_cert, ssl_key)
    elif domain:
        logger.info(
            "Admin panel domain set to %s. "
            "Set up Caddy to reverse proxy to this port. Example Caddyfile:\n"
            "  %s {\n"
            "      reverse_proxy localhost:%s\n"
            "  }\n"
            "Then run: caddy run",
            domain,
            domain,
            admin_cfg.get("port", 27017),
        )
    else:
        logger.warning(
            "Admin panel has no SSL configured (ssl_cert/ssl_key or domain). "
            "Running over plain HTTP. Passwords will be sent in cleartext!"
        )

    return app, ssl_context
