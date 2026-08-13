"""Session binding for the GM panel: one-time tokens, bound sessions, expiry.

`GMSession` owns a live `Client` reference, its WebSockets, and every
privileged action taken through it. It is the ONLY place in the panel that calls
`commands.call` (via `execute_command`/`execute_command_in_area`), always through
the GM's real, live `Client`, so every `mod_only(...)` check runs exactly as if
the GM had typed the command themselves.
"""

import asyncio
import secrets
import time
import uuid

from aiohttp import web

from server import commands
from server.exceptions import ClientError, ArgumentError, AreaError, ServerError

from server.web_view.gm_panel.commands_meta import CommandOutputScrubber
from server.remote_client import RemoteClient


class SessionInvalid(Exception):
    """
    Raised internally when a `GMSession` fails re-validation immediately before
    a privileged action. Route handlers turn this into a 401.
    """


class PendingLogin:
    """A single-use `/gmpanel` login token awaiting exchange for a session."""

    __slots__ = ("client", "bind_key", "expires_at")

    def __init__(self, client, bind_key, expires_at):
        self.client = client
        self.bind_key = bind_key
        self.expires_at = expires_at


class GMSession:
    """
    One GM's bound web session.

    Owns the live `Client` reference, this session's WebSocket connections, and
    every privileged action taken through it. Internals (`_client`, `_bind_key`,
    `_ws_connections`) are private; other code interacts with a session only
    through its public methods.
    """

    def __init__(self, server, client, bind_key, ttl):
        self._server = server
        self._client = client
        self._bind_key = bind_key
        self._ttl = ttl
        self._created_at = time.time()
        self._ws_connections = set()

    @property
    def bound_client(self):
        """The live `Client` this session is bound to (read-only)."""
        return self._client

    @property
    def created_at(self):
        return self._created_at

    @property
    def role(self):
        """The session access tier: "gm" (live client) or a remote role."""
        return "gm"

    @property
    def is_admin(self):
        """True only for password-login sessions of role == "admin"."""
        return False

    @property
    def user(self):
        """The login username (None for live-client /gmpanel sessions)."""
        return None

    def is_valid(self):
        """
        Re-check GM privilege against the *current* live state. Never cached --
        GM status can be revoked by someone else mid-session.
        """
        client = self._client
        server = self._server
        if client not in server.client_manager.clients:
            return False
        if getattr(client, "_gm_bind_key", None) != self._bind_key:
            return False
        if client.area is None:
            return False
        if not client.is_mod and client not in client.area.area_manager.owners:
            return False
        return True

    def current_hub(self):
        """The bound client's current hub (`AreaManager`). Always re-read live."""
        return self._client.area.area_manager

    def current_area(self):
        """The bound client's current `Area`. Always re-read live."""
        return self._client.area

    @property
    def can_travel(self):
        """Whether this session may move between hubs. GMs are hub-bound."""
        return False

    def available_hubs(self):
        """The hubs this session may operate in. A GM session sees only its own."""
        return [self.current_hub()]

    def travel_to_hub(self, hub_id):
        """Move this session's client to `hub_id` (overridden by `AdminSession`)."""
        raise ClientError("You must be authorized to do that.")

    def summary(self):
        """Small "who am I" dict, safe to hand to the browser."""
        client = self._client
        area = client.area
        hub = area.area_manager
        return {
            "client_id": client.id,
            "name": client.name,
            "showname": client.showname,
            "hub_id": hub.id,
            "hub_name": hub.name,
            "area_id": area.id,
            "is_mod": client.is_mod,
            "role": self.role,
        }

    def execute_command(self, cmd, arg):
        """
        Run an OOC command through the bound client and capture its output.

        This is the only place in the panel that calls `commands.call`, and it
        always passes the real bound `Client`, so every permission check the
        in-game command layer performs runs exactly as it would if the GM had
        typed the command themselves. The bound client's `send_ooc` is shadowed
        with an instance attribute for the duration of the call so its response
        is captured instead of printed into the GM's real AO chat window.

        GM sessions run their output through `CommandOutputScrubber`; the
        `AdminSession` override skips that scrub (admins are authorized to see
        ipid/hdid) and special-cases the `ooc` chat command.
        """
        if not self.is_valid():
            raise SessionInvalid()
        return CommandOutputScrubber.scrub(self._run_command(cmd, arg))

    def _run_command(self, cmd, arg):
        """Execute `cmd` through the bound client and return the raw output lines.

        Shared by `execute_command` (which scrubs) and `AdminSession` (which does
        not). Kept as a single code path so command dispatch, output capture, and
        the `send_ooc` shadowing are never duplicated.
        """
        client = self._client
        buffer = []
        original_send_ooc = client.send_ooc

        def capture(msg, *a, **kw):
            buffer.append(msg)

        client.send_ooc = capture
        try:
            commands.call(client, cmd, arg)
        except (ClientError, ArgumentError, AreaError, ServerError) as ex:
            buffer.append(f"[ERROR] {type(ex).__name__}: {ex}")
        finally:
            client.send_ooc = original_send_ooc
        return buffer

    def _area_in_scope(self, area):
        return area is not None and area.area_manager is self.current_hub()

    def _call_on_target_area(self, area, fn):
        """
        Run `fn(client)` with the bound client's `.area` temporarily shadowed
        to `area` (the target evidence list's owning area), restored in a
        `finally` block -- the same instance-attribute-shadow technique
        `execute_command` already uses for `send_ooc`.

        Every permission decision and side effect in `EvidenceList.login()`/
        `add_evidence()`/`edit_evidence()`/`del_evidence()` (evidence_mod, area
        ownership, `dark`, and the CM-notification text/recipients) is keyed off
        `client.area`, not off the evi_list's own owning area. Rebinding `.area`
        for the duration of the call makes `EvidenceList.login()`'s gating apply
        to the actual target area, matching what would happen if the GM had
        physically walked there and run the in-game command.

        `client.area` is a plain attribute and this call is fully synchronous
        with no `await` points, so the temporary rebind is invisible to every
        other coroutine on the single-threaded event loop.
        """
        client = self._client
        original_area = client.area
        client.area = area
        try:
            return fn(client)
        finally:
            client.area = original_area

    def execute_command_in_area(self, area, cmd, arg):
        """
        Run an OOC command through the bound client with `.area` temporarily
        shadowed to `area`, capturing its output exactly like `execute_command`
        -- this combines `_run_command` with `_call_on_target_area` for
        commands (area prefs, links, `/desc`, `/doc`, ...) that always act on
        `client.area` and take no area-id argument of their own, so the only
        way to target a *different* area through the real command layer is to
        make it temporarily believe that's where the GM is standing.

        Only ever call this with commands that are fully synchronous (no `await`
        points).
        """
        if not self.is_valid() or not self._area_in_scope(area):
            raise SessionInvalid()
        buffer = []

        def run(_client):
            # `_run_command` re-reads `self._client`, whose `.area` has been
            # shadowed to the target area by `_call_on_target_area` for the
            # duration of this call.
            buffer.extend(self._run_command(cmd, arg))

        self._call_on_target_area(area, run)
        return CommandOutputScrubber.scrub(buffer)

    def set_area_direct(self, area, attr, value, key=None):
        """
        Set a scalar `Area` attribute directly (or a dict entry, when `key` is
        given -- e.g. `area.triggers["join"]`), without a backing OOC command.
        Used for `background_dark`, `pos_dark`, `msg_delay`, clearing a minigame
        song, and clearing a trigger (there is no `/trigger <key>` clear form).

        The attribute is written only after the real bound client -- evaluated
        against the target area -- passes the same gate the
        `@mod_only(area_owners=True)` commands use. The attribute name is always
        chosen by `AreaRoutes.handle_edit_area` (via the schema), never by the
        client, so a bad `attr` can never escape to an arbitrary attribute write.
        """
        if not self.is_valid() or not self._area_in_scope(area):
            raise SessionInvalid()

        def apply(client):
            if not client.is_mod and client not in area.owners:
                raise ClientError("You do not own that area!")
            if key is not None:
                getattr(area, attr)[key] = value
            else:
                setattr(area, attr, value)
            return True

        return bool(self._call_on_target_area(area, apply))

    def edit_evidence_direct(self, area, demo_id, name, desc, image, pos="*"):
        """
        Edit a demo script's evidence entry directly.

        This bypasses `commands.call` (the one deliberate exception in the
        panel) only to avoid corrupting multi-line scripts through slash-command
        tokenization; `EvidenceList.login()`'s permission gating still applies
        since we pass the real bound client, evaluated against the target area.
        """
        if not self.is_valid() or not self._area_in_scope(area):
            raise SessionInvalid()
        ok = self._call_on_target_area(
            area, lambda c: area.evi_list.edit_evidence(c, demo_id, (name, desc, image, pos))
        )
        if ok:
            area.broadcast_evidence_list()
        return bool(ok)

    def add_evidence_direct(self, area, name, desc, image):
        if not self.is_valid() or not self._area_in_scope(area):
            raise SessionInvalid()
        ok = self._call_on_target_area(area, lambda c: area.evi_list.add_evidence(c, name, desc, image))
        if ok:
            area.broadcast_evidence_list()
        return bool(ok)

    def del_evidence_direct(self, area, demo_id):
        if not self.is_valid() or not self._area_in_scope(area):
            raise SessionInvalid()
        ok = self._call_on_target_area(area, lambda c: area.evi_list.del_evidence(c, demo_id))
        if ok:
            area.broadcast_evidence_list()
        return bool(ok)

    def set_evidence_props_direct(self, area, demo_id, props):
        """
        Apply property overrides (pos, can_hide_in, show_in_dark, can_take,
        editable, triggers) directly to an evidence item.

        AO only exposes these through HiddenCM `<...>` desc metadata, so there is
        no OOC command behind them -- mirroring `edit_evidence_direct`, this
        mutates the live `Evidence` object while still gating through
        `EvidenceList.login()` against the real bound client evaluated in the
        target area.
        """
        if not self.is_valid() or not self._area_in_scope(area):
            raise SessionInvalid()
        if demo_id < 0 or demo_id >= len(area.evi_list.evidences):
            return False

        def apply(client):
            if not area.evi_list.login(client):
                return False
            evi = area.evi_list.evidences[demo_id]
            if "pos" in props:
                # The `<owner=...>` value clients see (parse_desc in
                # evidence.py). Empty/None -> "all" so clearing the field
                # makes the evidence visible everywhere rather than nowhere.
                evi.pos = str(props["pos"] or "all")
            if "can_hide_in" in props:
                evi.can_hide_in = bool(props["can_hide_in"])
            if "show_in_dark" in props:
                try:
                    evi.show_in_dark = max(0, min(2, int(props["show_in_dark"])))
                except (TypeError, ValueError):
                    return False
            if "can_take" in props:
                evi.can_take = bool(props["can_take"])
            if "editable" in props:
                evi.editable = bool(props["editable"])
            if "triggers" in props:
                trigs = props["triggers"]
                if not isinstance(trigs, dict):
                    return False
                evi.triggers = {str(k): str(v) for k, v in trigs.items()}
            return True

        ok = self._call_on_target_area(area, apply)
        if ok:
            area.broadcast_evidence_list()
        return bool(ok)

    def add_ws(self, ws):
        self._ws_connections.add(ws)

    def remove_ws(self, ws):
        self._ws_connections.discard(ws)

    def push(self, frame):
        """Fan out an already-shaped frame (a dict) to every socket this session owns."""
        loop = asyncio.get_event_loop()
        for ws in list(self._ws_connections):
            if ws.closed:
                self._ws_connections.discard(ws)
                continue
            loop.call_soon(asyncio.ensure_future, ws.send_json(frame))

    def push_event(self, type_, data):
        """Fan out a server->client event to every WebSocket this session owns."""
        payload = {"type": type_, "data": data}
        loop = asyncio.get_event_loop()
        for ws in list(self._ws_connections):
            if ws.closed:
                self._ws_connections.discard(ws)
                continue
            loop.call_soon(asyncio.ensure_future, ws.send_json(payload))

    def expire(self, reason):
        """Notify and close every WebSocket this session owns, then go dark."""
        self.push_event("session_ended", {"reason": reason})
        loop = asyncio.get_event_loop()
        for ws in list(self._ws_connections):
            loop.call_soon(asyncio.ensure_future, ws.close())
        self._ws_connections.clear()


class RemoteSession(GMSession):
    """A password-login session backed by a synthetic ``RemoteClient``.

    Shares all of ``GMSession``'s command/evidence/WS machinery (``execute_command``,
    ``execute_command_in_area``, the evidence ``*_direct`` methods, WS plumbing) --
    it only re-binds validation and identity to the synthetic client, which is not a
    live player and never has a ``_gm_bind_key``. Role is ``"gm"`` (hub-bound);
    ``AdminSession`` is the server-scoped subclass.
    """

    def __init__(self, server, remote_client, user, ttl):
        super().__init__(server, remote_client, None, ttl)
        self._user = user
        self._ooc_listener = None
        self._ic_listener = None

    @property
    def user(self):
        return self._user

    def is_valid(self):
        """The remote client stays valid while it is still joined to the server."""
        client = self._client
        if client not in self._server.client_manager.clients:
            return False
        if client.area is None:
            return False
        return True

    def summary(self):
        client = self._client
        area = client.area
        hub = area.area_manager if area is not None else None
        return {
            "client_id": getattr(client, "id", -1),
            "name": getattr(client, "name", ""),
            "showname": getattr(client, "showname", ""),
            "hub_id": hub.id if hub is not None else -1,
            "hub_name": hub.name if hub is not None else "?",
            "area_id": area.id if area is not None else -1,
            "is_mod": getattr(client, "is_mod", False),
            "role": self.role,
            "user": self._user,
        }

    def set_monitor(self, kind, enabled):
        """Enable/disable forwarding of OOC or IC frames to this session's sockets.

        ``kind`` is ``"ooc"`` or ``"ic"``. Enabling joins the remote client to its
        area (so it receives OOC/IC) and installs a listener that forwards only the
        matching frame type; disabling removes it and leaves the area once neither
        monitor is active.
        """
        if kind not in ("ooc", "ic"):
            return
        attr = "_" + kind + "_listener"
        listener = getattr(self, attr)
        if enabled:
            if listener is None:
                def forward(entry):
                    if entry.get("type") == kind:
                        self.push(entry)

                listener = forward
                setattr(self, attr, listener)
                self._client.join_area()
                self._client.add_listener(listener)
        else:
            if listener is not None:
                self._client.remove_listener(listener)
                setattr(self, attr, None)
                if self._ooc_listener is None and self._ic_listener is None:
                    self._client.leave_area()

    def teardown(self):
        """Detach the synthetic client: leave its area, drop listeners, clear output."""
        client = self._client
        for listener in (self._ooc_listener, self._ic_listener):
            if listener is not None:
                try:
                    client.remove_listener(listener)
                except Exception:
                    pass
        try:
            client.leave_area()
        except Exception:
            pass
        try:
            client.clear()
        except Exception:
            pass
        try:
            client._listeners.clear()
        except Exception:
            pass


class AdminSession(RemoteSession):
    """A server-scoped admin session.

    Unlike ``RemoteSession`` (a ``role: gm`` login, bound to a single hub) and
    ``GMSession`` (a live in-game GM, also hub-bound), an admin may travel to any
    hub on the server and sees raw (un-scrubbed) command output -- admins are
    already authorized to view ipid/hdid. It also special-cases the ``ooc``
    console command to speak as ``[M]<name>`` in its current area.
    """

    @property
    def role(self):
        return "admin"

    @property
    def is_admin(self):
        return True

    @property
    def can_travel(self):
        return True

    def available_hubs(self):
        hub_manager = getattr(self._server, "hub_manager", None)
        if hub_manager is None:
            return [self.current_hub()]
        return list(hub_manager.hubs)

    def travel_to_hub(self, hub_id):
        for hub in self.available_hubs():
            if hub.id == hub_id:
                if hub is self.current_hub():
                    raise ClientError("User already in specified hub.")
                self._client.change_area(hub.default_area())
                if self._client.area.area_manager is not hub:
                    raise ClientError("Failed to travel to hub.")
                return hub
        raise AreaError("Targeted hub not found!")

    def execute_command(self, cmd, arg):
        if not self.is_valid():
            raise SessionInvalid()
        if cmd == "ooc":
            remote = self.bound_client
            name = ("[M]" + remote.name) if remote.is_mod else remote.name
            remote.area.send_command("CT", name, arg)
            return []
        return self._run_command(cmd, arg)


class GMSessionManager:
    """
    Mints one-time login tokens, exchanges them for bound `GMSession`s, looks
    sessions up by cookie, and invalidates them on disconnect or expiry. Owns
    `_sessions`/`_pending_tokens` privately -- no other class touches those
    dicts directly.
    """

    def __init__(self, server, config):
        self._server = server
        self._config = config
        self._sessions = {}
        self._pending_tokens = {}
        self._session_ttl = int(config.get("session_ttl_seconds", 28800))
        self._login_token_ttl = int(config.get("login_token_ttl_seconds", 60))
        self._sweep_handle = None
        self._remote_sessions = {}

        rl = config.get("rate_limit", {}) or {}
        self._rate_limit = {
            "max_attempts": int(rl.get("max_attempts", 10)),
            "window_seconds": int(rl.get("window_seconds", 300)),
            "lockout_seconds": int(rl.get("lockout_seconds", 300)),
        }
        self._users = self._parse_users(config.get("users", {}) or {})
        self._login_attempts = {}

    @property
    def session_ttl(self):
        return self._session_ttl

    @property
    def login_token_ttl(self):
        return self._login_token_ttl

    @staticmethod
    def _parse_users(raw_users):
        """Normalize ``gm_panel.users`` into ``{username: {password, role}}``."""
        users = {}
        for username, entry in (raw_users or {}).items():
            if isinstance(entry, dict):
                password = str(entry.get("password", ""))
                role = str(entry.get("role", "admin")).lower()
            else:
                password = str(entry)
                role = "admin"
            if role not in ("admin", "gm"):
                role = "admin"
            users[str(username)] = {"password": password, "role": role}
        return users

    def _is_rate_limited(self, ip):
        state = self._login_attempts.get(ip)
        if state is None:
            return False
        if time.time() < state.get("lockout_until", 0):
            return True
        self._login_attempts.pop(ip, None)
        return False

    def _record_failed_login(self, ip):
        now = time.time()
        state = self._login_attempts.get(ip)
        if state is None:
            state = {"failures": [], "lockout_until": 0}
            self._login_attempts[ip] = state
        window = self._rate_limit["window_seconds"]
        state["failures"] = [t for t in state["failures"] if now - t < window]
        state["failures"].append(now)
        if len(state["failures"]) >= self._rate_limit["max_attempts"]:
            state["lockout_until"] = now + self._rate_limit["lockout_seconds"]
            state["failures"] = []

    def _clear_login_attempts(self, ip):
        self._login_attempts.pop(ip, None)

    def login(self, username, password, ip):
        """Verify a username/password and mint a remote session.

        Returns ``(token, session, error)`` -- exactly one of ``token``/``error``
        is set. The synthetic ``RemoteClient`` is built per role:

        * ``admin`` -> ``is_mod=True`` (full server scope + admin log viewer)
        * ``gm``    -> ``is_mod=True, is_gm=True`` (the GM tabs, no log viewer)
        """
        ip = ip or "unknown"
        if self._is_rate_limited(ip):
            return None, None, "rate_limited"
        if not self._users:
            return None, None, "login_disabled"

        entry = self._users.get(str(username or ""))
        if entry is None or entry["password"] != str(password or ""):
            self._record_failed_login(ip)
            return None, None, "invalid_credentials"

        self._clear_login_attempts(ip)
        role = entry["role"]
        if role == "admin":
            remote = RemoteClient(self._server, is_mod=True, name="[ADMIN:%s]" % username)
            session = AdminSession(self._server, remote, str(username), self._session_ttl)
        else:
            remote = RemoteClient(
                self._server, is_mod=True, is_gm=True, name="[GM:%s]" % username
            )
            session = RemoteSession(self._server, remote, str(username), self._session_ttl)
        remote.join_area()
        token = secrets.token_urlsafe(32)
        self._remote_sessions[token] = session
        return token, session, None

    def start_sweep(self):
        """
        Schedule the periodic expiry sweep. Unlike `admin_panel.py`'s dead
        `_cleanup_sessions` (defined but never invoked), this one actually runs,
        re-scheduling itself every 60 seconds.
        """
        loop = asyncio.get_event_loop()
        self._sweep_handle = loop.call_later(60, self._sweep)

    def _sweep(self):
        now = time.time()
        expired_tokens = [
            t for t, s in self._sessions.items()
            if not s.is_valid() or (now - s.created_at > self._session_ttl)
        ]
        for t in expired_tokens:
            session = self._sessions.pop(t, None)
            if session is not None:
                session.expire("expired")

        remote_expired = [
            t for t, s in self._remote_sessions.items()
            if not s.is_valid() or (now - s.created_at > self._session_ttl)
        ]
        for t in remote_expired:
            session = self._remote_sessions.pop(t, None)
            if session is not None:
                session.expire("expired")
                session.teardown()

        stale_pending = [t for t, p in self._pending_tokens.items() if now > p.expires_at]
        for t in stale_pending:
            self._pending_tokens.pop(t, None)

        loop = asyncio.get_event_loop()
        self._sweep_handle = loop.call_later(60, self._sweep)

    def mint_login_token(self, client):
        """Generate a single-use token bound to `client`'s dynamic bind key."""
        if getattr(client, "_gm_bind_key", None) is None:
            client._gm_bind_key = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
        self._pending_tokens[token] = PendingLogin(
            client, client._gm_bind_key, time.time() + self._login_token_ttl
        )
        return token

    def exchange_token(self, token):
        pending = self._pending_tokens.pop(token, None)
        if pending is None:
            return None, None, "invalid_or_expired_token"
        if time.time() > pending.expires_at:
            return None, None, "invalid_or_expired_token"

        client = pending.client
        if getattr(client, "_gm_bind_key", None) != pending.bind_key:
            return None, None, "invalid_or_expired_token"
        if client not in self._server.client_manager.clients:
            return None, None, "invalid_or_expired_token"
        if client.area is None or (
            not client.is_mod and client not in client.area.area_manager.owners
        ):
            return None, None, "invalid_or_expired_token"

        session = GMSession(self._server, client, pending.bind_key, self._session_ttl)
        session_token = secrets.token_urlsafe(32)
        self._sessions[session_token] = session
        return session_token, session, None

    def get_session(self, token):
        """Look up and re-validate a session by its cookie token."""
        session = self._sessions.get(token)
        if session is None:
            session = self._remote_sessions.get(token)
        if session is None:
            return None
        if not session.is_valid() or (time.time() - session.created_at > self._session_ttl):
            self._sessions.pop(token, None)
            self._remote_sessions.pop(token, None)
            session.expire("expired")
            return None
        return session

    def remove_session(self, session):
        """
        Log out exactly this one session. Other sessions bound to the same
        client (e.g. the same GM's phone and laptop) are left alone.
        """
        for token, s in list(self._sessions.items()):
            if s is session:
                del self._sessions[token]
                return
        for token, s in list(self._remote_sessions.items()):
            if s is session:
                del self._remote_sessions[token]
                session.teardown()
                return

    def invalidate_for_client(self, client):
        """
        Kill every session bound to `client`, immediately. Called from the
        disconnect hook chain, before the client's id is recycled.
        """
        tokens = [t for t, s in self._sessions.items() if s.bound_client is client]
        for t in tokens:
            session = self._sessions.pop(t, None)
            if session is not None:
                session.expire("disconnected")

    def all_sessions(self):
        """Live sessions, for `GMPanelBridge` to scope broadcasts against."""
        return list(self._sessions.values()) + list(self._remote_sessions.values())

    def find_sessions_for_client(self, client):
        """Sessions specifically bound to `client` (used for `hub_switched`)."""
        return [s for s in self._sessions.values() if s.bound_client is client]

    def require(self, handler):
        """Decorator: require a valid `gm_session` cookie for an aiohttp handler."""
        async def wrapper(request):
            token = request.cookies.get("gm_session")
            session = self.get_session(token) if token else None
            if session is None:
                if request.path.startswith("/api/gm/") or request.path.startswith("/ws/gm/"):
                    return web.json_response({"error": "session_invalid"}, status=401)
                return web.HTTPFound("/")
            request["gm_session"] = session
            return await handler(request)
        return wrapper



