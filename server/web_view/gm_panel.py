"""
GM Control Panel web application.

A separate aiohttp app (own port, own session cookie/store) that lets an
in-game GM micromanage their hub through a browser: areas as a graph,
who's present, characters/character-data, GM-scoped OOC commands, and the
Automation Demos system.

Unlike `admin_panel.py`, this panel never runs commands through a synthetic
`RemoteClient`. Every privileged action executes through the GM's real,
live, in-game `Client` object (see `GMSession.execute_command`), so the
exact same `mod_only(area_owners=...)`/`mod_only(hub_owners=...)` checks the
command layer already performs are what gate the panel too -- there is no
separate permission system to keep in sync or get wrong.

Structured as small, single-purpose classes with constructor-injected
dependencies (see the class map in the design doc) rather than the
module-global style of `admin_panel.py`:

    GMPanelApp       -- aiohttp Application/routes/lifecycle
    GMPanelBridge     -- translates area/client hook calls into WS events
    GMSessionManager  -- token minting/exchange/expiry, session lookup
    GMSession         -- one GM's bound web session
    *Serializer       -- field-level whitelisting, one per object type
    CommandOutputScrubber -- last-resort ipid/hdid/IP redaction
    GMCommandCatalog  -- curated allowlist for the Commands tab
    *Routes           -- one handler class per tab

ipid/hdid/IP are never exposed to a GM: `ClientSerializer` is the only code
path allowed to turn a `Client` into JSON, the command catalog excludes any
command that could print those fields, and `CommandOutputScrubber` redacts
captured command output as a last-resort safety net.
"""

import asyncio
import json
import logging
import os
import re
import secrets
import ssl
import time
import uuid

import aiohttp
from aiohttp import web

from server import commands
from server.remote_client import RemoteClient
from server.exceptions import ClientError, ArgumentError, AreaError, ServerError
from server.constants import _SYSTEM_IPID, derelative
from server.script_runner import parse_demo_description
from server.scripting import live_get, resolve_value, live_sources, ScriptingError

logger = logging.getLogger("gm_panel")


class SessionInvalid(Exception):
    """
    Raised internally when a `GMSession` fails re-validation immediately
    before a privileged action. Route handlers turn this into a 401.
    """


# =============================================================================
# Serializers -- the only code allowed to turn live objects into JSON.
# =============================================================================


class ClientSerializer:
    """
    Converts a live `Client` into the GM-facing field whitelist.

    This is the ONLY place in the GM panel allowed to turn a `Client` into
    JSON -- no handler may call `vars(client)`/`client.__dict__` or hand-roll
    a client dict inline. That makes "ipid/hdid/ip can never leak to a GM" a
    structural property of the code rather than a discipline problem.
    """

    @staticmethod
    def to_dict(client):
        area = client.area
        hub = area.area_manager if area is not None else None
        return {
            "id": client.id,
            "char_id": client.char_id,
            "char_name": client.char_name,
            "showname": client.showname,
            "name": client.name,
            "iniswap": client.iniswap,
            "f_char_name": client.f_char_name,
            "pos": client.pos,
            "area_id": area.id if area is not None else -1,
            "hub_id": hub.id if hub is not None else -1,
            "is_mod": client.is_mod,
            "is_hub_gm": hub is not None and client in hub.owners,
            "is_area_cm": area is not None and client in area._owners,
            "is_afk": area is not None and client in area.afkers,
            "hidden": client.hidden,
            "software": client.software,
            "version": client.version,
        }


class AreaSerializer:
    """Converts a live `Area` into a graph node (§4 of the design doc)."""

    @staticmethod
    def _real_clients(area):
        return [
            c for c in area.clients
            if not isinstance(c, RemoteClient) and c.ipid != _SYSTEM_IPID
        ]

    @staticmethod
    def to_dict(area):
        real_clients = AreaSerializer._real_clients(area)
        client_ids = [c.id for c in real_clients]
        gm_ids = [c.id for c in real_clients if c in area.area_manager.owners]
        # `area.owners` (per `Area.owners`'s own definition) is
        # `area_manager.owners | area._owners` -- i.e. it also includes every
        # hub GM, not just this area's actual CMs. Match `ClientSerializer`'s
        # `is_area_cm` (which correctly uses `area._owners`) so the roster
        # doesn't stamp a CM badge on a hub GM who was never made CM here.
        cm_ids = [c.id for c in real_clients if c in area._owners]

        links = []
        for target_id_str, link in area.links.items():
            try:
                target_id = int(target_id_str)
            except (TypeError, ValueError):
                continue
            links.append({
                "target_id": target_id,
                "locked": bool(link.get("locked", False)),
                "hidden": bool(link.get("hidden", False)),
                "can_peek": bool(link.get("can_peek", True)),
                "has_password": bool(link.get("password", "")),
                "target_pos": link.get("target_pos", ""),
            })

        return {
            "id": area.id,
            "name": area.name,
            "background": area.background,
            "background_suffix": area.background_suffix,
            "overlay": area.overlay,
            "dark": area.dark,
            "locked": area.locked,
            "status": area.status,
            "client_ids": client_ids,
            "gm_client_ids": gm_ids,
            "cm_client_ids": cm_ids,
            "links": links,
            "fully_connected": len(area.links) == 0,
        }


class CharacterSlotSerializer:
    """Converts a hub's character list + live occupancy into slot dicts."""

    @staticmethod
    def slots_for_hub(hub):
        occupancy = {}
        for client in hub.clients:
            if isinstance(client, RemoteClient) or client.ipid == _SYSTEM_IPID:
                continue
            if client.char_id is not None and client.char_id >= 0:
                occupancy[client.char_id] = client.id

        slots = []
        for char_id, folder in enumerate(hub.char_list):
            occupied_by = occupancy.get(char_id)
            slots.append({
                "char_id": char_id,
                "folder": folder,
                "occupied_by_client_id": occupied_by,
                "taken": occupied_by is not None,
            })
        return slots


class CharacterDataSerializer:
    """Recursively coerces `AreaManager.character_data` values to JSON-safe types."""

    @staticmethod
    def sanitize(value):
        if isinstance(value, dict):
            return {str(k): CharacterDataSerializer.sanitize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [CharacterDataSerializer.sanitize(v) for v in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        try:
            return str(value)
        except Exception:
            return "<unserializable>"


class DemoSerializer:
    """Converts an area's evidence/demo entries into the Demos tab's shapes."""

    @staticmethod
    def _out_of_range_warnings(area, instructions):
        """
        Read-only mirror of `Area._warn_demo_out_of_range`'s check, without
        the side effect of broadcasting anything -- just reports the same
        warnings back to the caller so the panel can display them.
        """
        warnings = []
        nchars = len(area.area_manager.char_list)
        for instr in instructions:
            if instr[0] != "packet" or len(instr) < 3 or instr[1] != "MS":
                continue
            args = instr[2]
            if len(args) <= 8:
                continue
            try:
                cid = int(args[8])
            except (TypeError, ValueError):
                continue
            if cid == -1 or 0 <= cid < nchars:
                continue
            noun = "character" if nchars == 1 else "characters"
            warnings.append(
                f"MS packet references out-of-range char id {cid} "
                f"(this hub only has {nchars} {noun})."
            )
        return warnings

    @staticmethod
    def to_list_item(index, evidence, area):
        instructions = parse_demo_description(evidence.desc)
        runner = area.demo_runner
        is_running = bool(
            runner is not None
            and runner.running
            and getattr(runner, "gm_panel_demo_id", None) == index
        )
        return {
            "id": index,
            "name": evidence.name,
            "image": evidence.image,
            "pos": evidence.pos,
            "editable": evidence.editable,
            "can_take": evidence.can_take,
            "instruction_count": len(instructions),
            "parse_warnings": DemoSerializer._out_of_range_warnings(area, instructions),
            "is_running": is_running,
        }

    @staticmethod
    def to_detail(index, evidence, area):
        instructions = parse_demo_description(evidence.desc)
        return {
            "id": index,
            "name": evidence.name,
            "desc": evidence.desc,
            "image": evidence.image,
            "pos": evidence.pos,
            "editable": evidence.editable,
            "instructions": [list(instr) for instr in instructions],
            "parse_warnings": DemoSerializer._out_of_range_warnings(area, instructions),
        }


# =============================================================================
# Command output scrubbing / catalog
# =============================================================================


class CommandOutputScrubber:
    """
    Last-resort redaction pass over captured OOC command output lines.

    Serializers and the command catalog are the primary defenses against
    ipid/hdid/IP reaching a GM; this exists purely as defense in depth, in
    case a future cataloged command ever prints one of these incidentally
    (e.g. via a mod-visible branch that fires because the bound client
    also happens to be `is_mod`).
    """

    _IPV4_RE = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    )
    # Require at least 4 colon-separated groups so ordinary "HH:MM:SS"
    # timestamps (3 groups) don't get flagged as IPv6 addresses.
    _IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b")
    _IPID_LABEL_RE = re.compile(r"(?i)\bipid\b\s*[:#=]?\s*[\"']?[\w.\-]+")
    _HDID_LABEL_RE = re.compile(r"(?i)\bhdid\b\s*[:#=]?\s*[\"']?[\w.\-]+")
    _MOD_PROFILE_RE = re.compile(r"(?i)\bmod\s*profile(\s*name)?\s*[:#=]?\s*[\"']?[\w.\- ]+")

    @classmethod
    def scrub(cls, lines):
        return [cls._scrub_line(line) for line in lines]

    @classmethod
    def _scrub_line(cls, line):
        text = str(line)
        text = cls._IPID_LABEL_RE.sub("[redacted]", text)
        text = cls._HDID_LABEL_RE.sub("[redacted]", text)
        text = cls._MOD_PROFILE_RE.sub("[redacted]", text)
        text = cls._IPV6_RE.sub("[redacted]", text)
        text = cls._IPV4_RE.sub("[redacted]", text)
        return text


class CommandDescriptor:
    """Metadata for one command exposed on the Commands tab."""

    __slots__ = ("name", "usage", "description", "args", "destructive")

    def __init__(self, name, usage, description, args=None, destructive=False):
        self.name = name
        self.usage = usage
        self.description = description
        self.args = args or []
        self.destructive = destructive

    def to_dict(self):
        return {
            "name": self.name,
            "usage": self.usage,
            "description": self.description,
            "args": self.args,
            "destructive": self.destructive,
        }


class GMCommandCatalog:
    """
    Static, curated allowlist of OOC commands the Commands tab may run via
    `POST /api/gm/commands/run`.

    This is a UX curation aid, not a security boundary -- real authorization
    always happens live inside `commands.call()` via the bound client. It
    exists so the panel never even offers a command that could surface
    ipid/hdid/IP (`kick`, `ban`, `whois`, ...); those are permanently
    excluded regardless of their decorator.
    """

    _COMMANDS = [
        CommandDescriptor(
            "gm", "/gm [id]",
            "Make yourself or a listed client a GM of this hub.",
            [{"name": "id", "type": "client_id", "optional": True}],
            destructive=False,
        ),
        CommandDescriptor(
            "ungm", "/ungm <id>",
            "Revoke GM status from a client in this hub.",
            [{"name": "id", "type": "client_id"}],
            destructive=True,
        ),
        CommandDescriptor(
            "area", "/area <id>",
            "Move yourself to another area.",
            [{"name": "id", "type": "area_id"}],
            destructive=False,
        ),
        CommandDescriptor(
            "bg", "/bg <name>",
            "Change the background of your current area.",
            [{"name": "name", "type": "string"}],
            destructive=False,
        ),
        CommandDescriptor(
            "lock", "/lock", "Lock your current area.", [], destructive=True,
        ),
        CommandDescriptor(
            "unlock", "/unlock", "Unlock your current area.", [], destructive=False,
        ),
        CommandDescriptor(
            "area_mute", "/area_mute [id]",
            "Toggle IC mute for a client in this area.",
            [{"name": "id", "type": "client_id", "optional": True}],
            destructive=True,
        ),
        CommandDescriptor(
            "link", "/link <id> [locked] [hidden]",
            "Create a two-way link to another area.",
            [{"name": "id", "type": "area_id"}],
            destructive=False,
        ),
        CommandDescriptor(
            "unlink", "/unlink <id>",
            "Remove a link to another area.",
            [{"name": "id", "type": "area_id"}],
            destructive=True,
        ),
        CommandDescriptor(
            "onelink", "/onelink <id> [locked] [hidden]",
            "Create a one-way link to another area.",
            [{"name": "id", "type": "area_id"}],
            destructive=False,
        ),
        CommandDescriptor(
            "charlist", "/charlist [name]",
            "Switch this hub's character list (empty = server default).",
            [{"name": "name", "type": "string", "optional": True}],
            destructive=True,
        ),
        CommandDescriptor(
            "list_hubs", "/list_hubs",
            "List loadable hub templates on disk.", [], destructive=False,
        ),
        CommandDescriptor(
            "info", "/info", "Show this hub's info text.", [], destructive=False,
        ),
        CommandDescriptor(
            "trigger", "/trigger join|leave|present <id> <cmd> [args]",
            "Configure area/evidence event triggers.",
            [{"name": "raw", "type": "string"}],
            destructive=True,
        ),
    ]
    _ALLOWED = {d.name for d in _COMMANDS}

    @classmethod
    def is_allowed(cls, name):
        return name in cls._ALLOWED

    @classmethod
    def to_list(cls):
        return [d.to_dict() for d in cls._COMMANDS]


# =============================================================================
# Session binding
# =============================================================================


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

    Owns the live `Client` reference, this session's WebSocket connections,
    and every privileged action taken through it. Internals (`_client`,
    `_bind_key`, `_ws_connections`) are private; other code interacts with a
    session only through its public methods.
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

    def is_valid(self):
        """
        Re-check GM privilege against the *current* live state. Never
        cached -- GM status can be revoked by someone else mid-session.
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
        }

    def execute_command(self, cmd, arg):
        """
        Run an OOC command through the bound client and capture its output.

        This is the only place in the panel that calls `commands.call`, and
        it always passes the real bound `Client`, so every permission check
        the in-game command layer performs runs exactly as it would if the
        GM had typed the command themselves. The bound client's `send_ooc`
        is shadowed with an instance attribute for the duration of the call
        so its response is captured instead of printed into the GM's real
        AO chat window -- this touches nothing but this one object.
        """
        if not self.is_valid():
            raise SessionInvalid()
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
        return CommandOutputScrubber.scrub(buffer)

    def _area_in_scope(self, area):
        return area is not None and area.area_manager is self.current_hub()

    def _call_on_target_area(self, area, fn):
        """
        Run `fn(client)` with the bound client's `.area` temporarily shadowed
        to `area` (the target evidence list's owning area), restored in a
        `finally` block -- the same instance-attribute-shadow technique
        `execute_command` already uses for `send_ooc`.

        This matters because every permission decision and side effect in
        `EvidenceList.login()`/`add_evidence()`/`edit_evidence()`/
        `del_evidence()` (evidence_mod, area ownership, `dark`, and the
        CM-notification text/recipients) is keyed off `client.area`, not off
        the evi_list's own owning area. Without this, a hub GM standing in
        Area 1 editing Area 5's evidence would be gated by Area 1's
        `evidence_mod`/ownership instead of Area 5's -- silently bypassing
        e.g. an `evidence_mod = 'Mods'` restriction the hub owner set
        specifically on Area 5. Rebinding `.area` for the duration of the
        call makes `EvidenceList.login()`'s gating (and every notification
        it sends) apply to the actual target area, matching what would
        happen if the GM had physically walked there and run the in-game
        command.

        `client.area` is a plain attribute (not a property with side
        effects) and this call is fully synchronous with no `await` points,
        so the temporary rebind is invisible to every other coroutine on the
        single-threaded event loop.
        """
        client = self._client
        original_area = client.area
        client.area = area
        try:
            return fn(client)
        finally:
            client.area = original_area

    def edit_evidence_direct(self, area, demo_id, name, desc, image, pos="*"):
        """
        Edit a demo script's evidence entry directly.

        This bypasses `commands.call` (the one deliberate exception in the
        panel, see module docstring) only to avoid corrupting multi-line
        scripts through slash-command tokenization; `EvidenceList.login()`'s
        permission gating still applies since we pass the real bound client,
        evaluated against the target area (see `_call_on_target_area`).
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

    def add_ws(self, ws):
        self._ws_connections.add(ws)

    def remove_ws(self, ws):
        self._ws_connections.discard(ws)

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


class GMSessionManager:
    """
    Mints one-time login tokens, exchanges them for bound `GMSession`s,
    looks sessions up by cookie, and invalidates them on disconnect or
    expiry. Owns `_sessions`/`_pending_tokens` privately -- no other class
    touches those dicts directly.
    """

    def __init__(self, server, config):
        self._server = server
        self._config = config
        self._sessions = {}
        self._pending_tokens = {}
        self._session_ttl = int(config.get("session_ttl_seconds", 28800))
        self._login_token_ttl = int(config.get("login_token_ttl_seconds", 60))
        self._sweep_handle = None

    @property
    def session_ttl(self):
        return self._session_ttl

    @property
    def login_token_ttl(self):
        return self._login_token_ttl

    def start_sweep(self):
        """
        Schedule the periodic expiry sweep. Unlike `admin_panel.py`'s dead
        `_cleanup_sessions` (defined but never invoked), this one actually
        runs, re-scheduling itself every 60 seconds.
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
        """
        Consume a one-time login token and mint a session.

        Returns `(session_token, session, error)` -- exactly one of
        `(session_token, session)` or `error` is populated.
        """
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
            return None
        if not session.is_valid() or (time.time() - session.created_at > self._session_ttl):
            self._sessions.pop(token, None)
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
                break

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
        return list(self._sessions.values())

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


# =============================================================================
# Bridge: translates game-side hook calls into scoped WS events
# =============================================================================


class GMPanelBridge:
    """
    Translates raw hook calls from area/client code into structured event
    dicts and fans them out to every in-scope `GMSession`. Holds no session
    storage itself -- that's `GMSessionManager`'s job.
    """

    def __init__(self, server, session_manager, config):
        self._server = server
        self.session_manager = session_manager
        self._config = config

    @property
    def login_token_ttl(self):
        return self.session_manager.login_token_ttl

    def public_url_for_token(self, token):
        domain = self._config.get("domain")
        if domain:
            return f"https://{domain}/?token={token}"
        port = self._config.get("port", 27018)
        host = self._config.get("host", "0.0.0.0")
        has_ssl = bool(self._config.get("ssl_cert") and self._config.get("ssl_key"))
        scheme = "https" if has_ssl else "http"
        display_host = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
        return f"{scheme}://{display_host}:{port}/?token={token}"

    def _broadcast_to_hub(self, hub_ids, type_, data):
        for session in self.session_manager.all_sessions():
            if not session.is_valid():
                continue
            try:
                hub_id = session.current_hub().id
            except Exception:
                continue
            if hub_id in hub_ids:
                session.push_event(type_, data)

    def on_client_moved(self, client, old_area, new_area):
        """Hook: `Client.set_area` completed. The animation trigger."""
        if isinstance(client, RemoteClient):
            return
        from_hub_id = old_area.area_manager.id
        to_hub_id = new_area.area_manager.id
        data = {
            "client_id": client.id,
            "from_area_id": old_area.id,
            "to_area_id": new_area.id,
            "from_hub_id": from_hub_id,
            "to_hub_id": to_hub_id,
        }
        self._broadcast_to_hub({from_hub_id, to_hub_id}, "client_moved", data)
        if from_hub_id != to_hub_id:
            for session in self.session_manager.find_sessions_for_client(client):
                session.push_event("hub_switched", {
                    "new_hub_id": to_hub_id,
                    "new_hub_name": new_area.area_manager.name,
                })

    def on_client_present(self, client, area):
        """Hook: `Area.new_client` -- a client fully joined this area."""
        if isinstance(client, RemoteClient):
            return
        data = ClientSerializer.to_dict(client)
        self._broadcast_to_hub({area.area_manager.id}, "client_present", data)

    def on_client_absent(self, client, area):
        """Hook: `Area.remove_client` -- a client left this area."""
        if isinstance(client, RemoteClient):
            return
        data = {"client_id": client.id, "area_id": area.id}
        self._broadcast_to_hub({area.area_manager.id}, "client_absent", data)

    def on_client_disconnected(self, client):
        """Hook: `Server.remove_client`, before the client's id is recycled."""
        if isinstance(client, RemoteClient):
            return
        area = getattr(client, "area", None)
        if area is not None:
            data = {"client_id": client.id, "last_area_id": area.id}
            self._broadcast_to_hub({area.area_manager.id}, "client_disconnected", data)
        self.session_manager.invalidate_for_client(client)

    def on_hub_gm_roster_changed(self, area_manager):
        """Hook: `AreaManager.add_owner`/`remove_owner`."""
        gm_ids = [c.id for c in area_manager.real_owners()]
        data = {"hub_id": area_manager.id, "gm_client_ids": gm_ids}
        self._broadcast_to_hub({area_manager.id}, "hub_gm_roster_changed", data)

    def on_area_cm_roster_changed(self, area):
        """Hook: `Area.add_owner`/`remove_owner`."""
        cm_ids = [c.id for c in area.real_cms()]
        data = {"area_id": area.id, "cm_client_ids": cm_ids}
        self._broadcast_to_hub({area.area_manager.id}, "area_cm_roster_changed", data)

    def on_area_background_changed(self, area):
        """Hook: `Area.change_background`/`change_background_suffix`."""
        data = {"area_id": area.id, "background": area.background, "overlay": area.overlay}
        self._broadcast_to_hub({area.area_manager.id}, "background_changed", data)


# =============================================================================
# Misc helpers
# =============================================================================


def _list_yaml_names(path):
    """List `*.yaml` filenames (minus extension) under `path`, sorted."""
    try:
        names = [f[:-5] for f in os.listdir(path) if f.lower().endswith(".yaml")]
        return sorted(names)
    except FileNotFoundError:
        return []


def _command_ok(output):
    return not any(str(line).startswith("[ERROR]") for line in output)


def _command_response(output):
    return web.json_response({"ok": _command_ok(output), "output": output})


# =============================================================================
# Route handler classes -- one per tab, constructor-injected.
# =============================================================================


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


class AreaRoutes:
    """Areas tab: hub graph snapshot + background editing."""

    def __init__(self, session_manager, server, config):
        self._session_manager = session_manager
        self._server = server
        self._config = config

    async def handle_list_areas(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        areas = [AreaSerializer.to_dict(area) for area in hub.areas]
        return web.json_response({"hub_id": hub.id, "hub_name": hub.name, "areas": areas})

    async def handle_set_background(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400
            )
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        background = str(data.get("background", ""))
        overlay = str(data.get("overlay", ""))
        arg = f"{area_id} {background} {overlay}".strip()
        try:
            output = session.execute_command("gm_set_bg", arg)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_background_thumb_base_url(self, request):
        base_url = self._config.get("background_thumb_base_url", "")
        return web.json_response({"base_url": base_url})


class ClientRoutes:
    """Clients tab: roster + GM promote/demote."""

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    async def handle_list_clients(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        clients = [
            ClientSerializer.to_dict(c) for c in hub.clients
            if not isinstance(c, RemoteClient) and c.ipid != _SYSTEM_IPID
        ]
        return web.json_response({"hub_id": hub.id, "clients": clients})

    async def handle_promote(self, request):
        session = request["gm_session"]
        client_id = request.match_info["client_id"]
        try:
            output = session.execute_command("gm", client_id)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_demote(self, request):
        session = request["gm_session"]
        client_id = request.match_info["client_id"]
        try:
            output = session.execute_command("ungm", client_id)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)


class CommandRoutes:
    """Commands tab: the catalog + the free-form, allowlist-gated runner."""

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    async def handle_list_commands(self, request):
        return web.json_response({"commands": GMCommandCatalog.to_list()})

    async def handle_run_command(self, request):
        session = request["gm_session"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_request"}, status=400)

        cmd = str(data.get("cmd", "")).strip()
        arg = str(data.get("arg", ""))
        if not GMCommandCatalog.is_allowed(cmd):
            return web.json_response({"error": "command_not_allowed"}, status=403)

        try:
            output = session.execute_command(cmd, arg)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)


class CharacterRoutes:
    """Characters tab: char list slots, charlists, and Character Data CRUD."""

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    async def handle_list_characters(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        slots = CharacterSlotSerializer.slots_for_hub(hub)
        return web.json_response({
            "hub_id": hub.id, "char_list_ref": hub.char_list_ref, "slots": slots,
        })

    async def handle_list_charlists(self, request):
        return web.json_response({"charlists": _list_yaml_names("storage/charlists")})

    async def handle_apply_charlist(self, request):
        session = request["gm_session"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_request"}, status=400)
        name = str(data.get("name", ""))
        try:
            output = session.execute_command("charlist", name)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_character_data(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        data = CharacterDataSerializer.sanitize(hub.character_data)
        return web.json_response({"hub_id": hub.id, "character_data": data})

    async def handle_character_data_one(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        folder = request.match_info["folder"]
        if folder not in hub.character_data:
            return web.json_response({"error": "not_found"}, status=404)
        data = CharacterDataSerializer.sanitize(hub.character_data[folder])
        return web.json_response({"folder": folder, "data": data})

    async def handle_character_data_set(self, request):
        session = request["gm_session"]
        folder = request.match_info["folder"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request."]}, status=400)
        key = str(data.get("key", ""))
        value = str(data.get("value", ""))
        arg = f"{folder} {key} {value}".rstrip()
        try:
            output = session.execute_command("set_char_data", arg)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_character_data_get_key(self, request):
        session = request["gm_session"]
        folder = request.match_info["folder"]
        key = request.match_info["key"]
        try:
            output = session.execute_command("get_char_data", f"{folder} {key}")
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return web.json_response({"output": output})

    async def handle_snapshots_list(self, request):
        return web.json_response({"snapshots": _list_yaml_names("storage/character_data")})

    async def handle_snapshots_save(self, request):
        session = request["gm_session"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request."]}, status=400)
        name = str(data.get("name", ""))
        try:
            output = session.execute_command("save_character_data", name)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_snapshots_load(self, request):
        session = request["gm_session"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request."]}, status=400)
        name = str(data.get("name", ""))
        try:
            output = session.execute_command("load_character_data", name)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)


class DemoRoutes:
    """Demos / Automation tab."""

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    def _get_area(self, session, area_id):
        hub = session.current_hub()
        if area_id < 0 or area_id >= len(hub.areas):
            return None
        return hub.areas[area_id]

    def _resolve(self, session, request):
        """Resolve `{area_id}/{demo_id}` from the URL, or an error response."""
        try:
            area_id = int(request.match_info["area_id"])
            demo_id = int(request.match_info["demo_id"])
        except (KeyError, ValueError):
            return None, None, web.json_response({"error": "invalid_id"}, status=400)
        area = self._get_area(session, area_id)
        if area is None:
            return None, None, web.json_response({"error": "area_not_found"}, status=404)
        if demo_id < 0 or demo_id >= len(area.evi_list.evidences):
            return None, None, web.json_response({"error": "demo_not_found"}, status=404)
        return area, demo_id, None

    async def handle_list_demos(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)

        area_id_param = request.query.get("area_id")
        if area_id_param is not None:
            try:
                area_id = int(area_id_param)
            except ValueError:
                return web.json_response({"error": "invalid_area_id"}, status=400)
            area = self._get_area(session, area_id)
            if area is None:
                return web.json_response({"error": "area_not_found"}, status=404)
        else:
            area = session.current_area()

        demos = [
            DemoSerializer.to_list_item(i, evi, area)
            for i, evi in enumerate(area.evi_list.evidences)
        ]
        return web.json_response({"area_id": area.id, "area_name": area.name, "demos": demos})

    async def handle_get_demo(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        area, demo_id, err = self._resolve(session, request)
        if err is not None:
            return err
        evi = area.evi_list.evidences[demo_id]
        return web.json_response(DemoSerializer.to_detail(demo_id, evi, area))

    async def handle_put_demo(self, request):
        session = request["gm_session"]
        area, demo_id, err = self._resolve(session, request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        name = str(data.get("name", "*"))
        desc = str(data.get("desc", "*"))
        image = str(data.get("image", "*"))
        try:
            ok = session.edit_evidence_direct(area, demo_id, name, desc, image)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not ok:
            return web.json_response({"ok": False, "error": "not_authorized_or_invalid"}, status=403)
        return web.json_response({"ok": True})

    async def handle_new_demo(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"ok": False, "error": "invalid_area_id"}, status=400)
        area = self._get_area(session, area_id)
        if area is None:
            return web.json_response({"ok": False, "error": "area_not_found"}, status=404)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        name = str(data.get("name", ""))
        desc = str(data.get("desc", ""))
        image = str(data.get("image", ""))
        try:
            ok = session.add_evidence_direct(area, name, desc, image)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not ok:
            return web.json_response({"ok": False, "error": "not_authorized_or_invalid"}, status=403)
        # `add_evidence` always appends, so the new entry's id is the last
        # index. The frontend (DemosTab._saveScript) uses this to
        # immediately open the demo it just created.
        new_id = len(area.evi_list.evidences) - 1
        return web.json_response({"ok": True, "id": new_id})

    async def handle_delete_demo(self, request):
        session = request["gm_session"]
        area, demo_id, err = self._resolve(session, request)
        if err is not None:
            return err
        try:
            ok = session.del_evidence_direct(area, demo_id)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not ok:
            return web.json_response({"ok": False, "error": "not_authorized_or_invalid"}, status=403)
        return web.json_response({"ok": True})

    async def handle_run_demo(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
            demo_id = int(request.match_info["demo_id"])
        except ValueError:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid id."]}, status=400)
        area = self._get_area(session, area_id)
        if area is None:
            return web.json_response({"ok": False, "output": ["[ERROR] Area not found."]}, status=404)
        # `ooc_cmd_demo` always operates on `client.area` (it takes no area
        # argument), so the area shown/selected in the UI must actually be
        # the GM's live current area -- otherwise Run/Stop would silently
        # act on wherever the GM physically is instead of the tracked
        # `area_id`. Mirrors the same guard in handle_load_pack/save_pack.
        try:
            if area_id != session.current_area().id:
                return web.json_response(
                    {"ok": False, "output": ["[ERROR] That area is not your current area."]},
                    status=400,
                )
        except AttributeError:
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            output = session.execute_command("demo", str(demo_id + 1))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        ok = _command_ok(output)
        if ok and area.demo_runner is not None:
            # Dynamic attribute stamp (mirrors the `_gm_bind_key` pattern) so
            # the panel can report which evidence entry is currently running
            # -- `ScriptRunner` itself has no notion of "which evidence".
            area.demo_runner.gm_panel_demo_id = demo_id
        return web.json_response({"ok": ok, "output": output})

    async def handle_stop_demo(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        # `ooc_cmd_stop_demo` always operates on `client.area` -- see the
        # comment in handle_run_demo.
        try:
            if area_id != session.current_area().id:
                return web.json_response(
                    {"ok": False, "output": ["[ERROR] That area is not your current area."]},
                    status=400,
                )
        except AttributeError:
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            output = session.execute_command("stop_demo", "")
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_stop_all_demos(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        # Hub-wide stop still only makes sense relative to the GM's live
        # current area/hub -- same reasoning as handle_stop_demo.
        try:
            if area_id != session.current_area().id:
                return web.json_response(
                    {"ok": False, "output": ["[ERROR] That area is not your current area."]},
                    status=400,
                )
        except AttributeError:
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            output = session.execute_command("stop_demo", "all")
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_status(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"error": "invalid_area_id"}, status=400)
        area = self._get_area(session, area_id)
        if area is None:
            return web.json_response({"error": "area_not_found"}, status=404)

        runner = area.demo_runner
        if runner is None or not runner.running:
            return web.json_response({
                "area_id": area.id, "running": False, "index": 0,
                "instruction_count": 0, "steps": 0, "max_steps": 0,
                "labels": [], "modified_packets": [], "variables": {},
            })
        return web.json_response({
            "area_id": area.id,
            "running": runner.running,
            "index": runner.index,
            "instruction_count": len(runner.instructions),
            "steps": runner.steps,
            "max_steps": runner.max_steps,
            "labels": list(runner.labels.keys()),
            "modified_packets": list(runner.modified_packets),
            "variables": CharacterDataSerializer.sanitize(area.variables),
        })

    async def handle_eval(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)

        expression = str(data.get("expression", ""))
        area_id = data.get("area_id")
        if area_id is None:
            area = session.current_area()
        else:
            try:
                area = self._get_area(session, int(area_id))
            except (TypeError, ValueError):
                area = None
            if area is None:
                return web.json_response({"ok": False, "error": "area_not_found"}, status=404)

        try:
            value = live_get(expression, area, area.variables)
        except ScriptingError:
            try:
                value = resolve_value(expression, area.variables, live_sources(area))
            except ScriptingError as ex:
                return web.json_response({"ok": False, "error": str(ex)})
        return web.json_response({"ok": True, "value": value})

    async def handle_list_packs(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        client = session.bound_client
        hub = session.current_hub()
        if not (client.is_mod or client in hub.owners):
            return web.json_response({"error": "not_authorized"}, status=403)
        return web.json_response({"packs": _list_yaml_names("storage/evidence")})

    async def handle_load_pack(self, request):
        session = request["gm_session"]
        name = request.match_info["name"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request."]}, status=400)
        area_id = data.get("area_id")
        overlay = bool(data.get("overlay", False))
        if area_id is not None:
            try:
                if int(area_id) != session.current_area().id:
                    return web.json_response(
                        {"ok": False, "output": ["[ERROR] That area is not your current area."]},
                        status=400,
                    )
            except (TypeError, ValueError):
                return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        cmd = "evidence_overlay" if overlay else "evidence_load"
        try:
            output = session.execute_command(cmd, derelative(name))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_save_pack(self, request):
        session = request["gm_session"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request."]}, status=400)
        name = str(data.get("name", ""))
        area_id = data.get("area_id")
        if area_id is not None:
            try:
                if int(area_id) != session.current_area().id:
                    return web.json_response(
                        {"ok": False, "output": ["[ERROR] That area is not your current area."]},
                        status=400,
                    )
            except (TypeError, ValueError):
                return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        try:
            output = session.execute_command("evidence_save", derelative(name))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)


# =============================================================================
# App shell
# =============================================================================


class GMPanelApp:
    """
    Owns the aiohttp `Application`, its route table, static/template
    mounting, SSL setup, and lifecycle (`build()`). Composes everything
    else via constructor injection (`server`, `config`) -- no business
    logic of its own.
    """

    def __init__(self, server, config):
        self._server = server
        self._config = config
        self._templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        self._static_dir = os.path.join(os.path.dirname(__file__), "static")
        self._gm_html = None
        self._gm_login_html = None
        self._session_manager = GMSessionManager(server, config)
        self.bridge = GMPanelBridge(server, self._session_manager, config)

    def _load_template(self, name):
        path = os.path.join(self._templates_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def build(self):
        """Build and return `(aiohttp.web.Application, ssl_context_or_None)`."""
        self._gm_html = self._load_template("gm.html")
        self._gm_login_html = self._load_template("gm_login.html")

        logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

        auth_routes = AuthRoutes(
            self._session_manager, self._server, self.bridge,
            self._gm_html, self._gm_login_html,
        )
        area_routes = AreaRoutes(self._session_manager, self._server, self._config)
        client_routes = ClientRoutes(self._session_manager, self._server)
        command_routes = CommandRoutes(self._session_manager, self._server)
        character_routes = CharacterRoutes(self._session_manager, self._server)
        demo_routes = DemoRoutes(self._session_manager, self._server)

        require = self._session_manager.require

        app = web.Application()
        app["config"] = self._config
        app["server"] = self._server

        # Page + auth routes
        app.router.add_get("/", auth_routes.handle_root)
        app.router.add_post("/api/gm/session/exchange", auth_routes.handle_session_exchange)
        app.router.add_get("/api/gm/session", require(auth_routes.handle_session_get))
        app.router.add_post("/api/gm/logout", require(auth_routes.handle_logout))
        app.router.add_get("/ws/gm/live", require(auth_routes.handle_ws_live))

        # Areas tab
        app.router.add_get("/api/gm/areas", require(area_routes.handle_list_areas))
        app.router.add_get(
            "/api/gm/areas/background_thumb_base_url",
            require(area_routes.handle_background_thumb_base_url),
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/background", require(area_routes.handle_set_background)
        )

        # Clients tab
        app.router.add_get("/api/gm/clients", require(client_routes.handle_list_clients))
        app.router.add_post(
            "/api/gm/clients/{client_id}/gm", require(client_routes.handle_promote)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/ungm", require(client_routes.handle_demote)
        )

        # Commands tab
        app.router.add_get("/api/gm/commands", require(command_routes.handle_list_commands))
        app.router.add_post("/api/gm/commands/run", require(command_routes.handle_run_command))

        # Characters tab
        app.router.add_get(
            "/api/gm/characters", require(character_routes.handle_list_characters)
        )
        app.router.add_get("/api/gm/charlists", require(character_routes.handle_list_charlists))
        app.router.add_post(
            "/api/gm/charlists/apply", require(character_routes.handle_apply_charlist)
        )
        app.router.add_get(
            "/api/gm/character_data", require(character_routes.handle_character_data)
        )
        app.router.add_get(
            "/api/gm/character_data_snapshots", require(character_routes.handle_snapshots_list)
        )
        app.router.add_post(
            "/api/gm/character_data_snapshots/save",
            require(character_routes.handle_snapshots_save),
        )
        app.router.add_post(
            "/api/gm/character_data_snapshots/load",
            require(character_routes.handle_snapshots_load),
        )
        app.router.add_get(
            "/api/gm/character_data/{folder}/{key}",
            require(character_routes.handle_character_data_get_key),
        )
        app.router.add_post(
            "/api/gm/character_data/{folder}/set",
            require(character_routes.handle_character_data_set),
        )
        app.router.add_get(
            "/api/gm/character_data/{folder}",
            require(character_routes.handle_character_data_one),
        )

        # Demos tab -- literal routes registered before the dynamic
        # {demo_id} route so e.g. "status" isn't swallowed as a demo id.
        app.router.add_get("/api/gm/demos", require(demo_routes.handle_list_demos))
        app.router.add_post("/api/gm/demos/eval", require(demo_routes.handle_eval))
        app.router.add_get("/api/gm/demo_packs", require(demo_routes.handle_list_packs))
        app.router.add_post("/api/gm/demo_packs/save", require(demo_routes.handle_save_pack))
        app.router.add_post(
            "/api/gm/demo_packs/{name}/load", require(demo_routes.handle_load_pack)
        )
        app.router.add_get("/api/gm/demos/{area_id}/status", require(demo_routes.handle_status))
        app.router.add_post("/api/gm/demos/{area_id}/new", require(demo_routes.handle_new_demo))
        app.router.add_post(
            "/api/gm/demos/{area_id}/stop_all", require(demo_routes.handle_stop_all_demos)
        )
        app.router.add_post("/api/gm/demos/{area_id}/stop", require(demo_routes.handle_stop_demo))
        app.router.add_post(
            "/api/gm/demos/{area_id}/{demo_id}/run", require(demo_routes.handle_run_demo)
        )
        app.router.add_get(
            "/api/gm/demos/{area_id}/{demo_id}", require(demo_routes.handle_get_demo)
        )
        app.router.add_put(
            "/api/gm/demos/{area_id}/{demo_id}", require(demo_routes.handle_put_demo)
        )
        app.router.add_delete(
            "/api/gm/demos/{area_id}/{demo_id}", require(demo_routes.handle_delete_demo)
        )

        # Static assets -- same physical folder as admin_panel.py's, served
        # on a separate port, so gm.css/gm.js can't collide with admin's.
        app.router.add_static("/static", self._static_dir)

        self._session_manager.start_sweep()

        return app, self._build_ssl_context()

    def _build_ssl_context(self):
        ssl_cert = self._config.get("ssl_cert")
        ssl_key = self._config.get("ssl_key")
        domain = self._config.get("domain")

        if ssl_cert and ssl_key:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(ssl_cert, ssl_key)
            logger.info("GM panel SSL enabled (cert: %s, key: %s)", ssl_cert, ssl_key)
            return ctx

        if domain:
            logger.info(
                "GM panel domain set to %s. "
                "Set up Caddy to reverse proxy to this port. Example Caddyfile:\n"
                "  %s {\n"
                "      reverse_proxy localhost:%s\n"
                "  }\n"
                "Then run: caddy run",
                domain, domain, self._config.get("port", 27018),
            )
            return None

        logger.warning(
            "GM panel has no SSL configured (ssl_cert/ssl_key or domain). "
            "Running over plain HTTP."
        )
        return None
