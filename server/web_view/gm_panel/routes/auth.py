"""Session lifecycle routes: root page, token exchange, heartbeat, logout, WS."""

import json

import aiohttp
from aiohttp import web


class AuthRoutes:
    """Session lifecycle: root page, token exchange, heartbeat, logout, WS."""

    def __init__(self, session_manager, server, bridge, gm_html, gm_login_html):
        self._session_manager = session_manager
        self._server = server
        self._bridge = bridge
        self._gm_html = gm_html
        self._gm_login_html = gm_login_html

    async def handle_root(self, request):
        token = request.cookies.get("gm_session")
        session = self._session_manager.get_session(token) if token else None
        if session is None:
            return web.Response(text=self._gm_login_html, content_type="text/html")
        return web.Response(text=self._gm_html, content_type="text/html")

    async def handle_session_exchange(self, request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)

        token = str(data.get("token", ""))
        if not token:
            return web.json_response(
                {"ok": False, "error": "invalid_or_expired_token"}, status=401
            )

        session_token, session, error = self._session_manager.exchange_token(token)
        if session is None:
            return web.json_response(
                {"ok": False, "error": error or "invalid_or_expired_token"}, status=401
            )

        response = web.json_response({"ok": True, "gm": session.summary()})
        gm_cfg = request.app["config"]
        has_ssl = bool(gm_cfg.get("ssl_cert") and gm_cfg.get("ssl_key"))
        response.set_cookie(
            "gm_session", session_token, httponly=True, samesite="Lax",
            secure=has_ssl, max_age=self._session_manager.session_ttl,
        )
        return response

    async def handle_login(self, request):
        """Username/password login for remote admin / remote GM access.

        Admins get a session immediately; ``gm`` logins return the allowed hub
        list (``needs_hub: true``) and wait for ``handle_hub_login`` to claim one.
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)

        username = str(data.get("username", ""))
        password = str(data.get("password", ""))
        ip = request.remote
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip() or ip

        result, error = self._session_manager.login(username, password, ip)
        if result is None:
            status = {
                "invalid_credentials": 401,
                "rate_limited": 429,
                "login_disabled": 403,
                "all_hubs_occupied": 409,
            }
            return web.json_response(
                {"ok": False, "error": error or "login_failed"},
                status=status.get(error, 401),
            )

        if "session" in result:
            return self._session_response(request, result["token"], result["session"])

        # gm role: hand back the allowed hubs for the picker -- no cookie yet.
        return web.json_response({
            "ok": True,
            "needs_hub": True,
            "pre_auth": result["pre_auth"],
            "hubs": result["hubs"],
            "ttl": result["ttl"],
        })

    async def handle_hub_login(self, request):
        """Second phase of a ``gm`` login: claim one of the allowed hubs."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)

        pre_auth = str(data.get("pre_auth", ""))
        try:
            hub_id = int(data.get("hub_id"))
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "invalid_hub"}, status=400)

        result, error = self._session_manager.complete_hub_login(pre_auth, hub_id)
        if result is None:
            status = {
                "invalid_or_expired_token": 401,
                "invalid_hub": 400,
                "hub_occupied": 409,
                "already_bound_hub": 409,
            }
            return web.json_response(
                {"ok": False, "error": error or "login_failed"},
                status=status.get(error, 401),
            )

        return self._session_response(request, result["token"], result["session"])

    def _session_response(self, request, token, session):
        """Build the ``{ok, gm}`` payload with the ``gm_session`` cookie set."""
        response = web.json_response({"ok": True, "gm": session.summary()})
        gm_cfg = request.app["config"]
        has_ssl = bool(gm_cfg.get("ssl_cert") and gm_cfg.get("ssl_key"))
        response.set_cookie(
            "gm_session", token, httponly=True, samesite="Lax",
            secure=has_ssl, max_age=self._session_manager.session_ttl,
        )
        return response

    async def handle_session_get(self, request):
        session = request["gm_session"]
        return web.json_response({"ok": True, "gm": session.summary()})

    async def handle_logout(self, request):
        session = request["gm_session"]
        self._session_manager.remove_session(session)
        response = web.json_response({"ok": True})
        response.del_cookie("gm_session")
        return response

    async def handle_ws_live(self, request):
        session = request["gm_session"]
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        session.add_ws(ws)

        client = session.bound_client
        try:
            hub = client.area.area_manager
            await ws.send_json({
                "type": "hello",
                "data": {
                    "gm_client_id": client.id,
                    "hub_id": hub.id,
                    "hub_name": hub.name,
                    "area_id": client.area.id,
                },
            })
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                    except Exception:
                        continue
                    if payload.get("type") == "ping":
                        await ws.send_json({"type": "pong", "data": {}})
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        finally:
            session.remove_ws(ws)
        return ws
