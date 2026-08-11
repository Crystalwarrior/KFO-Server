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
    CommandLister     -- auto-generated ooc_cmd_ reference (UX aid, not a
                         gate) for the Commands tab, built from
                         `server/commands/__init__.py`'s own submodules
    *Routes           -- one handler class per tab

ipid/hdid/IP are never exposed to a GM: `ClientSerializer` is the only code
path allowed to turn a `Client` into JSON, and `CommandOutputScrubber`
redacts captured command output as a last-resort safety net. The command
lister is a UX aid only -- it does not gate what `POST
/api/gm/commands/run` will execute; the live `mod_only(...)` checks inside
the command layer itself are the only real gate (see `CommandRoutes`).
"""

import asyncio
import inspect
import json
import logging
import os
import re
import secrets
import shlex
import shutil
import ssl
import time
import uuid

import aiohttp
import oyaml as yaml
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
    def links_to_list(area):
        """
        Build the JSON link list for `area`, keyed off its own (directed)
        `links` dict. Shared by `to_dict` (graph snapshot) and
        `AreaDetailSerializer`/the link-editing endpoints so there is exactly
        one place that knows the link dict's field names.
        """
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
                "evidence": [int(e) for e in link.get("evidence", [])],
            })
        return links

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

        return {
            "id": area.id,
            "name": area.name,
            "background": area.background,
            "background_suffix": area.background_suffix,
            "overlay": area.overlay,
            "dark": area.dark,
            "locked": area.locked,
            "status": area.status,
            # List of position strings, e.g. ["def", "pro"]; empty means "all
            # positions available". The graph needs this (not just the
            # inspector) so node header background images can prefer
            # `pos_lock[0]`'s asset over the generic witness-stand fallback.
            "pos_lock": [str(p) for p in area.pos_lock],
            "client_ids": client_ids,
            "gm_client_ids": gm_ids,
            "cm_client_ids": cm_ids,
            "links": AreaSerializer.links_to_list(area),
            "fully_connected": len(area.links) == 0,
        }


# Mirrors `ooc_cmd_area_pref`'s own hardcoded `cm_allowed` list
# (server/commands/hubs.py) exactly -- this copy is a UI hint only (it
# decides which prefs the Areas tab badges "[gm]"); the *real* gate is
# `ooc_cmd_area_pref` re-checking this same list live every time
# `execute_command_in_area(area, "area_pref", ...)` actually runs.
AREA_PREF_CM_ALLOWED = frozenset([
    "showname_changes_allowed",
    "shouts_allowed",
    "jukebox",
    "non_int_pres_only",
    "blankposting_allowed",
    "blankposting_forced",
    "hide_clients",
    "music_autoplay",
    "replace_music",
    "client_music",
    "can_dj",
    "music_locked",
    "hidden",
    "can_whisper",
    "can_wtce",
    "can_spectate",
    "can_getarea",
    "can_cross_swords",
    "can_scrum_debate",
    "can_panic_talk_action",
    "bg_lock",
    "force_sneak",
    "present_reveals_evidence",
    "ooc_actions_enabled",
    "medieval_mode",
])


class AreaDetailSerializer:
    """
    Converts a live `Area` into the Areas tab's per-area inspector payload:
    a small allowlist of command-backed scalar fields, every boolean pref
    (dynamically enumerated -- see `AREA_PREF_CM_ALLOWED`), and the full
    directed link list. Like `AreaSerializer`/`ClientSerializer`, this is the
    only place allowed to turn this slice of `Area` into JSON.
    """

    # Non-boolean scalar fields safe to expose read-only in the inspector.
    # Every attribute name here has been verified to exist on `Area`
    # (server/area.py `Area.__init__`) or as a computed `@property`.
    #
    # `abbreviation`/`ambience`/`broadcast_list` were added by the same audit
    # that added `pos_lock` editing (see `EDITABLE_FIELDS` below): a diff of
    # every non-boolean instance attribute `Area.__init__` sets against what
    # this tuple already exposed. See that audit's notes for the full list of
    # attributes considered and why each was included or left out -- nothing
    # here is moderator-only or exposes ipid/hdid/IP.
    _SCALAR_FIELDS = (
        "name", "background", "background_suffix", "overlay", "dark",
        "locked", "status", "doc", "desc", "move_delay", "max_players",
        "evidence_mod", "pos_lock", "abbreviation", "ambience", "broadcast_list",
    )

    # Fields from `_SCALAR_FIELDS` that have a real command behind them,
    # reachable via `AreaRoutes.handle_edit_area`. Everything else in
    # `_SCALAR_FIELDS` is read-only in the inspector.
    #
    # `pos_lock` routes through the *real* `/pos_lock` / `/pos_lock_clear`
    # commands (see `handle_edit_area`), same as every other entry here --
    # there is no separate write path that bypasses `ooc_cmd_pos_lock`'s own
    # permission check or its area-is-`dark` special case (in a dark area,
    # `/pos_lock <arg>` sets `pos_dark` instead of `pos_lock`, exactly as it
    # would if the GM had typed the command themselves).
    EDITABLE_FIELDS = frozenset(["name", "desc", "doc", "max_players", "status", "pos_lock"])

    @staticmethod
    def _prefs(area):
        prefs = []
        for attr_name in sorted(area.__dict__.keys()):
            if attr_name.startswith("_"):
                continue
            value = area.__dict__[attr_name]
            if type(value) is not bool:
                continue
            prefs.append({
                "name": attr_name,
                "value": value,
                "gm_only": attr_name not in AREA_PREF_CM_ALLOWED,
            })
        return prefs

    @staticmethod
    def to_dict(area):
        fields = {}
        for name in AreaDetailSerializer._SCALAR_FIELDS:
            value = getattr(area, name, None)
            # `broadcast_list` holds live `Area` OBJECTS, not ids or strings
            # (see `ooc_cmd_area_broadcast` in server/commands/areas.py and
            # its hub-scoped twin in server/commands/hubs.py:
            # `client.area.broadcast_list = <result of get_areas_by_args>`,
            # a list of `Area`). `Area` defines no `__str__`/`__repr__`, so
            # without this, the generic list coercion below would call
            # `str(area_obj)` and leak a raw
            # `<server.area.Area object at 0x...>` memory address to the
            # browser instead of anything useful. Reduce to area ids first
            # so it serializes exactly like `pos_lock` (a list of strings)
            # and never leaks a live object.
            if name == "broadcast_list" and isinstance(value, list):
                value = [getattr(v, "id", v) for v in value]
            # `pos_lock`/`broadcast_list` are lists (of position strings /
            # area ids respectively); everything else here is a str/int.
            # Coerce defensively so a future non-JSON-safe Area attribute
            # added to `_SCALAR_FIELDS` can't leak an unexpected type to the
            # browser.
            if isinstance(value, list):
                value = [str(v) for v in value]
            elif not isinstance(value, (str, int, float, bool)) and value is not None:
                value = str(value)
            fields[name] = value

        return {
            "id": area.id,
            "fields": fields,
            "editable_fields": sorted(AreaDetailSerializer.EDITABLE_FIELDS),
            "prefs": AreaDetailSerializer._prefs(area),
            "links": AreaSerializer.links_to_list(area),
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


class EvidenceSerializer:
    """
    Converts an area's evidence entries into the Evidence tab's shapes.

    The Evidence tab is, under the hood, an editor for evidence items whose
    `desc` field holds a demo script (see `docs/demo_scripting.md`); the
    underlying `/demo` command and `ScriptRunner` machinery are unchanged,
    only the panel's user-facing vocabulary is "evidence" now.
    """

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
            "can_hide_in": bool(evidence.can_hide_in),
            "show_in_dark": int(evidence.show_in_dark),
            "triggers": dict(evidence.triggers or {}),
            "instruction_count": len(instructions),
            "parse_warnings": EvidenceSerializer._out_of_range_warnings(area, instructions),
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
            "can_take": evidence.can_take,
            "can_hide_in": bool(evidence.can_hide_in),
            "show_in_dark": int(evidence.show_in_dark),
            "triggers": dict(evidence.triggers or {}),
            "instructions": [list(instr) for instr in instructions],
            "parse_warnings": EvidenceSerializer._out_of_range_warnings(area, instructions),
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


class CommandLister:
    """
    Auto-generated command reference for the Commands tab, replacing the
    old hand-curated `GMCommandCatalog`.

    Built directly from `server.commands`' own submodules
    (`server/commands/__init__.py`'s `submodules()`) and each submodule's
    `__all__` list -- there is no separate, hand-maintained list to fall
    out of sync with the command layer. Every `ooc_cmd_*` name reachable
    through `server.commands` shows up here, grouped by the submodule it's
    defined in, with a summary/usage pulled straight from the command
    function's own docstring via `inspect.getdoc`.

    This is a UX aid ONLY -- `POST /api/gm/commands/run` (`CommandRoutes`)
    does not consult it and will run *any* command name, listed here or
    not. Authorization always happens live inside `commands.call()` via the
    bound client: a command's own `mod_only(...)` decorator (or lack
    thereof) is the only thing deciding whether a given GM may run it, same
    as if they had typed it in their AO client. `CommandOutputScrubber`
    (still applied to every captured output line) is the defense-in-depth
    backstop against a command incidentally printing ipid/hdid/IP -- not
    this list.

    Cached at `_cache` after the first build -- command functions (and
    therefore their docstrings/`__all__` membership) don't change at
    runtime except through the server-wide `/reload_commands`-style path
    that ends up calling `server.commands.reload()` (see
    `server/tsuserver.py`), which is rare and lives well outside this
    module (`gm_panel.py` has no cheap hook into it without reaching into
    `tsuserver.py`, which is out of this file's scope). A GM panel process
    that's been up since before such a reload will keep serving the
    pre-reload command list until the panel process itself restarts --
    documented staleness, not a correctness hazard, since `/reload`-style
    reloads only swap in fresh function objects for the *same* command
    names.
    """

    _cache = None

    @staticmethod
    def _describe(name, func):
        doc = inspect.getdoc(func) or ""
        lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
        summary = lines[0] if lines else ""
        usage_lines = [ln for ln in lines if "usage:" in ln.lower()]
        prefix = "ooc_cmd_"
        display_name = name[len(prefix):] if name.startswith(prefix) else name
        return {
            "name": display_name,
            "summary": summary,
            "usage": " ".join(usage_lines),
        }

    @classmethod
    def _build(cls):
        groups = []
        for module in commands.submodules():
            module_name = module.__name__.split(".")[-1]
            names = getattr(module, "__all__", None)
            if names is None:
                names = [n for n in dir(module) if n.startswith("ooc_cmd_")]
            cmd_list = []
            for name in names:
                if not name.startswith("ooc_cmd_"):
                    continue
                func = getattr(module, name, None)
                if func is None:
                    continue
                cmd_list.append(cls._describe(name, func))
            cmd_list.sort(key=lambda c: c["name"])
            groups.append({"module": module_name, "commands": cmd_list})
        groups.sort(key=lambda g: g["module"])
        return groups

    @classmethod
    def to_groups(cls):
        if cls._cache is None:
            cls._cache = cls._build()
        return cls._cache

    @classmethod
    def invalidate(cls):
        """
        Cache-bust hook for a future cheap `server.commands.reload()`
        integration (see class docstring) -- not currently wired to
        anything, since that reload path lives in `tsuserver.py`.
        """
        cls._cache = None


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

    def execute_command_in_area(self, area, cmd, arg):
        """
        Run an OOC command through the bound client with `.area` temporarily
        shadowed to `area`, capturing its output exactly like
        `execute_command` -- this is `execute_command` and
        `_call_on_target_area` combined into one call for commands (area
        prefs, links, `/desc`, `/doc`, ...) that always act on
        `client.area` and take no area-id argument of their own, so the
        only way to target a *different* area through the real command
        layer is to make it temporarily believe that's where the GM is
        standing.

        Only ever call this with commands that are fully synchronous (no
        `await` points) -- every caller in `AreaRoutes` has been checked
        against its source in `server/commands/hubs.py` and
        `server/commands/area_access.py` for exactly that property. A
        command that does yield to the event loop must instead be run via
        `execute_command` on the client's true current area (or refactored
        into something else entirely), because a shadowed `.area` would
        then be visible to other coroutines running on the same loop
        in-between yields.
        """
        if not self.is_valid() or not self._area_in_scope(area):
            raise SessionInvalid()
        buffer = []

        def run(client):
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

        self._call_on_target_area(area, run)
        return CommandOutputScrubber.scrub(buffer)

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

    def set_evidence_props_direct(self, area, demo_id, props):
        """
        Apply property overrides (pos, can_hide_in, show_in_dark, can_take,
        editable, triggers) directly to an evidence item.

        AO only exposes these through HiddenCM `<...>` desc metadata, so
        there is no OOC command behind them -- mirroring
        `edit_evidence_direct`, this mutates the live `Evidence` object
        while still gating through `EvidenceList.login()` against the real
        bound client evaluated in the target area.
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

    def push_areas_changed(self, hub_id):
        """
        Called directly by `AreaRoutes` (not a hook off `area.py`/
        `area_manager.py` -- those files belong to other packages) after
        every successful area/pref/link mutation the panel makes, so every
        open panel on this hub refetches its areas snapshot instead of
        needing a manual reload.
        """
        self._broadcast_to_hub({hub_id}, "areas_changed", {"hub_id": hub_id})


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


# A "subpath" data name may descend at most this many directory levels
# below a kind's own directory -- kept in lockstep with `_split_data_name`'s
# "1-4 segments" rule (up to 3 subdirectory segments + 1 filename segment).
_MAX_DATA_SUBDIR_DEPTH = 3


def _walk_data_files(base):
    """
    Recursively list `*.yaml` files under `base` (a kind's own directory),
    as relative paths WITHOUT the `.yaml` extension using "/" separators
    (e.g. `"events/mystery"`), sorted.

    Any directory literally named `read_only` is skipped entirely (neither
    descended into nor listed) -- the read-only tree for kinds that have
    one is listed separately, flat, exactly as before (see
    `_list_data_files`). Recursion never follows symlinks and stops
    descending once `_MAX_DATA_SUBDIR_DEPTH` directory levels below `base`
    have already been listed, matching the max segment count
    `_split_data_name` will accept for a write.
    """
    base = os.path.normpath(base)
    try:
        base_depth = base.count(os.sep)
    except Exception:
        return []
    results = []
    for root, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if d != "read_only"]
        depth = root.count(os.sep) - base_depth
        if depth >= _MAX_DATA_SUBDIR_DEPTH:
            # Already at the deepest allowed subdirectory level -- list
            # files here, but don't descend any further.
            dirs[:] = []
        rel_dir = os.path.relpath(root, base)
        for f in files:
            if not f.lower().endswith(".yaml"):
                continue
            stem = f[:-5]
            if rel_dir == ".":
                results.append(stem)
            else:
                results.append("/".join(rel_dir.split(os.sep) + [stem]))
    return sorted(results)


def _command_ok(output):
    return not any(str(line).startswith("[ERROR]") for line in output)


def _command_response(output):
    return web.json_response({"ok": _command_ok(output), "output": output})


# -- A4: generic GM-facing yaml file storage ---------------------------------
#
# kind -> directory map, verified against the command bodies that actually
# read/write each of these (see `HubDataRoutes` docstring for the file:line
# citations). This is the ONLY place in the panel that knows these five
# directories; every data-file endpoint goes through the helpers below
# instead of hand-building a path.
DATA_KIND_DIRS = {
    "hubs": "storage/hubs",
    "musiclists": "storage/musiclists",
    "charlists": "storage/charlists",
    "character_data": "storage/character_data",
    "evidence": "storage/evidence",
}

# Kinds that have a `read_only/` subdirectory of non-editable files (verified:
# `storage/hubs/read_only/`, `storage/musiclists/read_only/` both exist and
# are handled by `/save_hub`/`/load_hub` and `/musiclist_save`/hub-musiclist
# loading respectively; `storage/charlists`, `storage/character_data`,
# `storage/evidence` have no such subdirectory -- confirmed against
# `ooc_cmd_charlist(s)`, `ooc_cmd_{save,load}_character_data`, and
# `ooc_cmd_evidence_{save,load,overlay}`, none of which ever reference a
# `read_only` path).
DATA_KIND_READONLY_SUBDIR = frozenset(["hubs", "musiclists"])

# Deliberately NOT `derelative()` (which only strips `../`/`..\\` substrings
# and is easy to reason past) -- a strict allowlist of the characters a
# panel-submitted file name SEGMENT may contain. Every `/api/gm/data/...`
# and `/api/gm/hub/...` file name is validated segment-by-segment against
# this before it ever touches the filesystem -- see `_split_data_name`.
_DATA_NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,64}$")


def _split_data_name(name):
    """
    Validate a (possibly multi-segment, "/"-separated) panel-submitted data
    file name -- e.g. `"events/mystery"` -- and return its list of
    segments, or `None` if invalid.

    A valid name has 1-4 segments, EVERY segment matching `_DATA_NAME_RE`
    (which -- since it only allows `[A-Za-z0-9 _-]` -- already rejects an
    empty segment, `"."`, `".."`, any segment containing `/` itself, and
    any non-ASCII/unicode segment; there is no separate traversal check
    needed because those strings simply cannot match the allowlist). No
    segment may literally be `"read_only"` (case-sensitive, matching the
    on-disk directory name), so a multi-segment name submitted through this
    path can never address a kind's read-only tree -- only the existing
    single-segment lookup (which explicitly checks the `read_only/`
    subdirectory first) can ever resolve there.
    """
    if not isinstance(name, str) or name == "":
        return None
    segments = name.split("/")
    if not (1 <= len(segments) <= 4):
        return None
    for seg in segments:
        if not _DATA_NAME_RE.match(seg):
            return None
        if seg == "read_only":
            return None
    return segments


_MAX_DATA_FILE_BYTES = 256 * 1024

# `GMPanelApp` runs on the same single asyncio event loop as the entire game
# server (it is built inside `tsuserver.py`, no separate thread/process), so
# a synchronous `yaml.safe_load()` of arbitrary client-submitted text must
# never be allowed to take unbounded time/memory. None of the five kinds
# this API writes (hub/musiclist/charlist/character_data/evidence yaml) has
# any legitimate use for YAML anchors (`&name`) or aliases (`*name`), so
# `_BoundedSafeLoader` rejects them outright rather than trying to bound
# "how much" aliasing is acceptable -- the safest fix for a construct this
# endpoint never needs. It also caps the total number of nodes composed and
# the nesting depth, as a second line of defense against a document that is
# merely huge or absurdly deeply nested (independent of aliasing) getting
# past the 256 KB byte cap's rough per-node budget, or overflowing the
# recursive composer's call stack. With aliasing banned outright, a
# composed node's cost is inherently linear in the source bytes that
# produced it (no aliasing left to multiply it), so these are set well
# above what any legitimate 256 KB document of this API's yaml kinds would
# ever need -- they exist to catch pathological input, not ordinary large
# files.
_MAX_YAML_NODES = 200000
# Composing one YAML nesting level costs a handful of Python stack frames
# (this loader's own `compose_node` override, `Composer.compose_node`, and
# `compose_sequence_node`/`compose_mapping_node`), so this must stay well
# under `sys.getrecursionlimit()` (1000 by default) for the depth check
# itself to ever fire instead of a raw `RecursionError` -- which
# `_bounded_safe_load()`'s caller also guards against separately, but
# failing cleanly here is preferable.
_MAX_YAML_DEPTH = 100


class _YamlTooComplex(yaml.YAMLError):
    """Raised by `_BoundedSafeLoader` when a document is rejected as too complex."""


class _BoundedSafeLoader(yaml.SafeLoader):
    """
    `yaml.SafeLoader` variant hardened for parsing arbitrary, untrusted,
    client-submitted YAML on the server's single event loop:

    - Anchors and aliases are rejected outright (`&name` / `*name`) -- none
      of this API's yaml kinds ever need them, so there is no reason to
      accept the risk of alias-driven amplification at all.
    - Composition aborts once more than `_MAX_YAML_NODES` nodes have been
      visited, or more than `_MAX_YAML_DEPTH` levels of nesting are seen,
      bounding total parse work/stack depth independent of the 256 KB byte
      cap enforced separately by the caller.
    """

    def compose_node(self, parent, index):
        if self.check_event(yaml.events.AliasEvent):
            raise _YamlTooComplex("YAML aliases ('*name') are not permitted here.")
        event = self.peek_event()
        if getattr(event, "anchor", None):
            raise _YamlTooComplex("YAML anchors ('&name') are not permitted here.")

        count = getattr(self, "_gm_node_count", 0) + 1
        self._gm_node_count = count
        if count > _MAX_YAML_NODES:
            raise _YamlTooComplex("YAML document is too complex (too many nodes).")

        depth = getattr(self, "_gm_depth", 0) + 1
        self._gm_depth = depth
        if depth > _MAX_YAML_DEPTH:
            raise _YamlTooComplex("YAML document is nested too deeply.")
        try:
            return super().compose_node(parent, index)
        finally:
            self._gm_depth -= 1


def _bounded_safe_load(content):
    """
    `yaml.safe_load()`, but using `_BoundedSafeLoader` so anchors/aliases
    and unbounded size/nesting can't force unbounded CPU/memory work or
    stack depth on the server's single event loop. Raises `yaml.YAMLError`
    (including `_YamlTooComplex`) on invalid or rejected input, exactly
    like `yaml.safe_load()` raises `yaml.YAMLError` on invalid input.

    Also converts a raw `RecursionError` -- which could in principle still
    reach the interpreter's recursion limit before `_MAX_YAML_DEPTH` fires,
    depending on the exact per-level stack-frame cost -- into the same
    `_YamlTooComplex` (a `yaml.YAMLError`), so callers only ever need to
    catch one exception type for "reject this content".
    """
    try:
        return yaml.load(content, Loader=_BoundedSafeLoader)
    except RecursionError:
        raise _YamlTooComplex("YAML document is nested too deeply.")


def _path_inside(root_realpath, candidate_path):
    """True iff `os.path.realpath(candidate_path)` is `root_realpath` or lands inside it."""
    real = os.path.realpath(candidate_path)
    return real == root_realpath or real.startswith(root_realpath + os.sep)


def _list_data_files(kind):
    """
    `[{"name": ..., "read_only": bool}, ...]` for every yaml file under
    `kind`'s directory, sorted editable-first then by name. Returns `None`
    for an unknown `kind`.

    The editable side is listed RECURSIVELY (`_walk_data_files`; any
    `read_only` directory encountered during that recursion is skipped, at
    any depth), so a file saved into a subfolder (e.g.
    `"events/mystery.yaml"`) shows up as `"events/mystery"`. The
    `read_only/` subdirectory itself (for kinds that have one) is still
    listed separately, flat/non-recursive, exactly as before -- read-only
    files stay top-level.
    """
    base = DATA_KIND_DIRS.get(kind)
    if base is None:
        return None
    files = [{"name": n, "read_only": False} for n in _walk_data_files(base)]
    if kind in DATA_KIND_READONLY_SUBDIR:
        files += [
            {"name": n, "read_only": True}
            for n in _list_yaml_names(os.path.join(base, "read_only"))
        ]
    files.sort(key=lambda f: (f["read_only"], f["name"].lower()))
    return files


def _resolve_existing_data_path(kind, name):
    """
    Resolve `name` (validated via `_split_data_name` -- 1-4 "/"-separated
    segments, none of them `read_only`) to an existing yaml file under
    `kind`'s directory -- checking the `read_only/` subdirectory first for
    a single-segment `name` when `kind` has one, then the editable
    directory (recursively, for multi-segment names) -- verifying
    containment via `os.path.realpath` at every step. Returns the real
    path, or `None` if `kind`/`name` are invalid or no such file exists.
    """
    base = DATA_KIND_DIRS.get(kind)
    if base is None:
        return None
    segments = _split_data_name(name)
    if segments is None:
        return None
    root = os.path.realpath(base)
    candidates = []
    if len(segments) == 1 and kind in DATA_KIND_READONLY_SUBDIR:
        candidates.append(os.path.join(base, "read_only", f"{segments[0]}.yaml"))
    rel_parts = segments[:-1] + [f"{segments[-1]}.yaml"]
    candidates.append(os.path.join(base, *rel_parts))
    for candidate in candidates:
        if _path_inside(root, candidate) and os.path.isfile(os.path.realpath(candidate)):
            return os.path.realpath(candidate)
    return None


def _safe_data_write_path(kind, name):
    """
    Resolve the EDITABLE-directory write target for `name` (validated via
    `_split_data_name`) under `kind`, for `PUT /api/gm/data/{kind}/file`
    (and the hub/charlist/music save flows that reuse this same helper).
    Returns `(path, None)` on success, or `(None, error_code)` on failure.
    Never returns a path inside a `read_only/` subdirectory, and refuses to
    shadow an existing read-only file of the same (single-segment) name
    (mirroring `/save_hub`'s own "already exists and it is read-only"
    guard).

    For a multi-segment `name`, creates any missing intermediate
    directories (`os.makedirs(..., exist_ok=True)`) AFTER the name has
    been fully validated and containment-checked -- never before.
    """
    base = DATA_KIND_DIRS.get(kind)
    if base is None:
        return None, "unknown_kind"
    segments = _split_data_name(name)
    if segments is None:
        return None, "invalid_name"

    root = os.path.realpath(base)
    if len(segments) == 1 and kind in DATA_KIND_READONLY_SUBDIR:
        ro_root = os.path.realpath(os.path.join(base, "read_only"))
        ro_candidate = os.path.join(base, "read_only", f"{segments[0]}.yaml")
        if _path_inside(ro_root, ro_candidate) and os.path.isfile(os.path.realpath(ro_candidate)):
            return None, "read_only_exists"

    rel_parts = segments[:-1] + [f"{segments[-1]}.yaml"]
    path = os.path.join(base, *rel_parts)
    if not _path_inside(root, path):
        return None, "invalid_name"

    if len(segments) > 1:
        parent_dir = os.path.dirname(path)
        # Re-check containment on the directory we're about to create,
        # not just the final file path, before touching the filesystem.
        if not _path_inside(root, parent_dir):
            return None, "invalid_name"
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError:
            return None, "write_failed"

    return os.path.realpath(path), None


def _hub_data_gate_ok(session):
    """
    True iff the session's bound client may manage this hub's saved
    GM-facing data files.

    REPLICATES the gate every relevant command already enforces --
    `@mod_only(hub_owners=True)` on `/save_hub`, `/load_hub`, `/charlist`,
    `/hub_musiclist`, `/save_character_data`, `/load_character_data`
    (`client.is_mod or client in client.area.area_manager.owners`, see
    `mod_only()` in `server/commands/__init__.py`) -- evaluated live so a
    GM demoted mid-session is rejected immediately rather than relying on
    the command layer to catch it after the fact.
    """
    client = session.bound_client
    hub = session.current_hub()
    return client.is_mod or client in hub.owners


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
    """
    Areas tab: hub graph snapshot, per-area inspector (detail/prefs/edit),
    hub-level area management (create/remove/swap), and link management.
    """

    # `AreaDetailSerializer.EDITABLE_FIELDS` -> (command, value -> arg)
    # mapping for `handle_edit_area`. `name`/`max_players`/`status` pass
    # the raw value straight through as the command's argument; `desc`/
    # `doc` need the clear-command substituted when the new value is empty
    # since `/desc`/`/doc` with no argument only *displays* the current
    # value instead of clearing it (see `ooc_cmd_desc`/`ooc_cmd_doc`).
    _LINK_BOOL_PROPS = {
        "lock": ("link_lock", "link_unlock"),
        "hide": ("link_hide", "link_unhide"),
        "peekable": ("link_peekable", "link_unpeekable"),
    }

    def __init__(self, session_manager, server, config, bridge=None):
        self._session_manager = session_manager
        self._server = server
        self._config = config
        self._bridge = bridge

    # -- shared helpers -----------------------------------------------

    def _areas_snapshot(self, hub):
        return [AreaSerializer.to_dict(area) for area in hub.areas]

    def _area_from_request(self, session, request, key="area_id"):
        """Resolve `{area_id}` from the URL against the session's current hub."""
        try:
            area_id = int(request.match_info[key])
        except (KeyError, ValueError):
            return None
        hub = session.current_hub()
        if area_id < 0 or area_id >= len(hub.areas):
            return None
        return hub.areas[area_id]

    def _push_areas_changed(self, session):
        if self._bridge is None:
            return
        try:
            hub_id = session.current_hub().id
        except Exception:
            return
        self._bridge.push_areas_changed(hub_id)

    # -- graph snapshot / background (existing) ------------------------

    async def handle_list_areas(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        areas = self._areas_snapshot(hub)
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
        if _command_ok(output):
            self._push_areas_changed(session)
        return _command_response(output)

    async def handle_background_thumb_base_url(self, request):
        base_url = self._config.get("background_thumb_base_url", "")
        return web.json_response({"base_url": base_url})

    # -- A2: area detail + editing --------------------------------------

    async def handle_area_detail(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        area = self._area_from_request(session, request)
        if area is None:
            return web.json_response({"error": "area_not_found"}, status=404)
        return web.json_response({"ok": True, "area": AreaDetailSerializer.to_dict(area)})

    async def handle_set_pref(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        area = self._area_from_request(session, request)
        if area is None:
            return web.json_response({"ok": False, "output": ["[ERROR] Area not found."]}, status=404)
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        pref = str(data.get("pref", "")).strip()
        value = bool(data.get("value", False))

        # `ooc_cmd_area_pref` does `getattr(client.area, cmd)` with no
        # default and only catches `ValueError`/`AreaError`/`ClientError`
        # -- an unknown attribute name would raise a bare `AttributeError`
        # straight through `execute_command_in_area`. Verify it's a real,
        # currently-boolean attribute ourselves first so a bad `pref` comes
        # back as a clean 400 instead of a 500.
        current = area.__dict__.get(pref)
        if pref.startswith("_") or type(current) is not bool:
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] Unknown preference: {pref}"]}, status=400
            )

        arg = f"{pref} {'on' if value else 'off'}"
        try:
            output = session.execute_command_in_area(area, "area_pref", arg)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if _command_ok(output):
            self._push_areas_changed(session)
        return _command_response(output)

    async def handle_edit_area(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        area = self._area_from_request(session, request)
        if area is None:
            return web.json_response({"ok": False, "output": ["[ERROR] Area not found."]}, status=404)
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        field = str(data.get("field", ""))
        value = str(data.get("value", ""))

        if field not in AreaDetailSerializer.EDITABLE_FIELDS:
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] Unsupported field: {field}"]}, status=400
            )

        try:
            if field == "name":
                # `/area_rename` supports an explicit `[aid]` prefix, so we
                # can target this area directly without shadowing
                # `client.area` at all -- and doing it this way sidesteps
                # `ooc_cmd_area_rename`'s own "does the name start with a
                # number?" sniffing (it would otherwise mistake a name like
                # "5 Guard Posts" for an area-id prefix).
                output = session.execute_command("area_rename", f"{area.id} {value}")
            elif field == "desc":
                cmd, arg = ("desc_clear", "") if value == "" else ("desc", value)
                output = session.execute_command_in_area(area, cmd, arg)
            elif field == "doc":
                cmd, arg = ("cleardoc", "") if value == "" else ("doc", value)
                output = session.execute_command_in_area(area, cmd, arg)
            elif field == "max_players":
                output = session.execute_command_in_area(area, "max_players", value)
            elif field == "pos_lock":
                # Mirrors `/pos_lock`/`/pos_lock_clear` exactly: empty value
                # clears the lock (all positions available again), non-empty
                # value is passed straight through as `/pos_lock`'s own
                # comma-or-space-separated argument -- `ooc_cmd_pos_lock`
                # does its own parsing/dedup/lowercasing, so there's nothing
                # left for this route to do beyond picking which command to
                # call.
                if value.strip() == "":
                    output = session.execute_command_in_area(area, "pos_lock_clear", "")
                else:
                    output = session.execute_command_in_area(area, "pos_lock", value)
            else:  # "status"
                output = session.execute_command_in_area(area, "status", value)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)

        if _command_ok(output):
            self._push_areas_changed(session)
        return _command_response(output)

    # -- A3: hub-level area management -----------------------------------

    async def handle_create_area(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        name = str(data.get("name", ""))
        insert_at = data.get("insert_at")

        try:
            output = session.execute_command("area_create", name)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not _command_ok(output):
            return _command_response(output)

        hub = session.current_hub()
        # `/area_create` always appends, so the new area is the last one.
        if insert_at is not None:
            try:
                target = int(insert_at)
            except (TypeError, ValueError):
                target = None
            if target is not None:
                idx = len(hub.areas) - 1
                target = max(0, min(target, idx))
                while idx > target:
                    swap_output = session.execute_command("area_swap", f"{idx} {idx - 1}")
                    output = output + swap_output
                    if not _command_ok(swap_output):
                        break
                    idx -= 1

        self._push_areas_changed(session)
        return web.json_response({
            "ok": True, "output": output,
            "hub_id": hub.id, "hub_name": hub.name, "areas": self._areas_snapshot(hub),
        })

    async def handle_remove_area(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400
            )
        try:
            output = session.execute_command("area_remove", str(area_id))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)

        hub = session.current_hub()
        if _command_ok(output):
            self._push_areas_changed(session)
        return web.json_response({
            "ok": _command_ok(output), "output": output,
            "hub_id": hub.id, "hub_name": hub.name, "areas": self._areas_snapshot(hub),
        })

    async def handle_swap_areas(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        try:
            a = int(data.get("a"))
            b = int(data.get("b"))
        except (TypeError, ValueError):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] 'a' and 'b' must be area ids."]}, status=400
            )
        try:
            output = session.execute_command("area_swap", f"{a} {b}")
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)

        hub = session.current_hub()
        if _command_ok(output):
            self._push_areas_changed(session)
        return web.json_response({
            "ok": _command_ok(output), "output": output,
            "hub_id": hub.id, "hub_name": hub.name, "areas": self._areas_snapshot(hub),
        })

    # -- A4: link management ---------------------------------------------

    async def _resolve_link_request(self, request):
        """
        Shared prefix for every `/links/*` endpoint: pull the session and
        source area out of the request, parse the JSON body, and parse
        `target_id`. Returns `(session, area, data, target_id, None)` on
        success, or `(None, None, None, None, error_response)` on failure.
        """
        session = request["gm_session"]
        if not session.is_valid():
            return None, None, None, None, web.json_response(
                {"error": "session_invalid"}, status=401
            )
        area = self._area_from_request(session, request)
        if area is None:
            return None, None, None, None, web.json_response(
                {"ok": False, "output": ["[ERROR] Area not found."]}, status=404
            )
        try:
            data = await request.json()
        except Exception:
            return None, None, None, None, web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        try:
            target_id = int(data.get("target_id"))
        except (TypeError, ValueError):
            return None, None, None, None, web.json_response(
                {"ok": False, "output": ["[ERROR] 'target_id' must be an area id."]}, status=400
            )
        return session, area, data, target_id, None

    async def _link_mutation(self, request, arg_builder):
        """
        Shared body for the two-way `/links/*` endpoints: resolve the
        source area, parse `target_id`, run `cmd` through
        `execute_command_in_area`, and return the updated link list.
        """
        session, area, data, target_id, err = await self._resolve_link_request(request)
        if err is not None:
            return err

        try:
            resolved_cmd, arg = arg_builder(data, target_id)
        except ValueError as ex:
            return web.json_response({"ok": False, "output": [f"[ERROR] {ex}"]}, status=400)

        try:
            output = session.execute_command_in_area(area, resolved_cmd, arg)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if _command_ok(output):
            self._push_areas_changed(session)
        return web.json_response({
            "ok": _command_ok(output), "output": output,
            "area_id": area.id, "links": AreaSerializer.links_to_list(area),
        })

    async def _link_add_or_remove_one_way(self, session, area, target_id, is_add):
        """
        A2: the `two_way=false` path for `/links/add|remove` -- performs the
        one-way `Area.link()`/`Area.unlink()` primitive directly on `area`
        (never touching the target area's own link dict), bypassing
        `commands.call` entirely.

        The permission gate below REPLICATES `/unlink`'s exactly (verified
        against `server/commands/area_access.py`): `@mod_only(area_owners=True)`
        gates the source area (`client.is_mod or client in area.owners`),
        and the command's own per-target loop body additionally requires
        `client.is_mod or client in <target>.owners`. `/link`'s gate is
        identical up front (only the one-way vs. two-way primitive call
        differs), so this same check covers both add and remove.
        """
        hub = session.current_hub()
        if target_id < 0 or target_id >= len(hub.areas):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Target area not found."]}, status=404
            )
        target_area = hub.areas[target_id]
        client = session.bound_client

        if not (client.is_mod or client in area.owners):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] You must be authorized to do that."]},
                status=403,
            )
        if not (client.is_mod or client in target_area.owners):
            return web.json_response(
                {"ok": False, "output": [
                    f"[ERROR] You don't own area [{target_area.id}] {target_area.name}."
                ]},
                status=403,
            )

        if is_add:
            area.link(target_id)
            output = [
                f"Area {area.name} has been linked with {target_id} (one-way)."
            ]
        else:
            try:
                area.unlink(target_id)
            except AreaError as ex:
                return web.json_response({"ok": False, "output": [f"[ERROR] {ex}"]}, status=400)
            output = [
                f"Area {area.name} has been unlinked from {target_id} (one-way)."
            ]

        # Only the source area's link dict changed -- broadcast/refresh
        # accordingly, never the target's.
        area.broadcast_area_list()
        self._push_areas_changed(session)
        return web.json_response({
            "ok": True, "output": output,
            "area_id": area.id, "links": AreaSerializer.links_to_list(area),
        })

    async def _handle_link_add_or_remove(self, request, is_add):
        session, area, data, target_id, err = await self._resolve_link_request(request)
        if err is not None:
            return err

        two_way = bool(data.get("two_way", True))
        if not two_way:
            return await self._link_add_or_remove_one_way(session, area, target_id, is_add)

        cmd = "link" if is_add else "unlink"
        try:
            output = session.execute_command_in_area(area, cmd, str(target_id))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if _command_ok(output):
            self._push_areas_changed(session)
        return web.json_response({
            "ok": _command_ok(output), "output": output,
            "area_id": area.id, "links": AreaSerializer.links_to_list(area),
        })

    async def handle_link_add(self, request):
        return await self._handle_link_add_or_remove(request, is_add=True)

    async def handle_link_remove(self, request):
        return await self._handle_link_add_or_remove(request, is_add=False)

    async def handle_link_set(self, request):
        def build(data, target_id):
            prop = str(data.get("prop", ""))
            if prop in self._LINK_BOOL_PROPS:
                on_cmd, off_cmd = self._LINK_BOOL_PROPS[prop]
                cmd = on_cmd if bool(data.get("value")) else off_cmd
                return cmd, str(target_id)
            if prop == "pos":
                pos = str(data.get("value", ""))
                return "link_pos", f"{target_id} {pos}".rstrip()
            if prop == "evidence":
                # `value` is a list of 0-indexed evidence ids -- the same
                # numbering `EvidenceSerializer`'s `id` field uses -- for
                # consistency with the rest of the panel's evidence
                # endpoints. `/link_evidence` itself is 1-indexed on the
                # wire (it displays/parses evidence *numbers*), so we
                # translate here rather than exposing that command-layer
                # quirk to the frontend.
                raw = data.get("value") or []
                if not isinstance(raw, list):
                    raise ValueError("'value' must be a list of evidence ids for prop=evidence.")
                try:
                    evi_ids = [str(int(v) + 1) for v in raw]
                except (TypeError, ValueError):
                    raise ValueError("Evidence ids must be numbers.")
                if not evi_ids:
                    return "unlink_evidence", str(target_id)
                return "link_evidence", f"{target_id} " + " ".join(evi_ids)
            raise ValueError(f"Unsupported link property: {prop}")

        return await self._link_mutation(request, build)


class ClientRoutes:
    """
    Clients tab: roster, GM promote/demote, and per-player management
    actions (private message, teleport).

    Every management action below dispatches through the real command
    layer via `execute_command` -- `/pm` (messaging.py) and `/area_kick`
    (areas.py, `@mod_only(area_owners=True)`, which a hub-owner passes via
    `Area.owners = area_manager.owners | _owners` and a mod passes via
    `is_mod`) -- so the exact same permission checks and side effects run
    as if the GM had typed the command in their AO client.
    """

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

    async def handle_pm(self, request):
        session = request["gm_session"]
        client_id = request.match_info["client_id"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        message = str(data.get("message", ""))
        if not message.strip():
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Message must not be empty."]}, status=400
            )
        # `/pm <id> <message>` -- the id is scoped to the GM's current hub
        # by `get_targets`'s default (non-`all_hub`) search, matching the
        # roster this tab displays.
        try:
            output = session.execute_command("pm", f"{client_id} {message}")
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_teleport_to_area(self, request):
        session = request["gm_session"]
        client_id = request.match_info["client_id"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        try:
            area_id = int(data.get("area_id"))
        except (TypeError, ValueError):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] 'area_id' must be an area id."]}, status=400
            )
        # `/area_kick <id> <destination> [target_pos]` -- the command's own
        # gate (`@mod_only(area_owners=True)`) and its "can't kick to an
        # area you don't own as a CM" check both apply as if the GM had
        # typed it, and the destination id resolves against the GM's hub.
        pos = str(data.get("pos", "") or "")
        arg = f"{client_id} {area_id} {pos}".rstrip()
        try:
            output = session.execute_command("area_kick", arg)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_teleport_here(self, request):
        session = request["gm_session"]
        client_id = request.match_info["client_id"]
        try:
            # `/area_kick <id>` with no destination defaults the target to
            # the GM's own current area -- i.e. "teleport to me"/arrive.
            output = session.execute_command("area_kick", str(client_id))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)


class CommandRoutes:
    """
    Commands tab: the auto-generated command list (`CommandLister`, not a
    whitelist) + the free-form command runner.

    `CommandLister` is UX curation only -- it is not consulted to decide
    what a GM can run. The *only* gate on what a GM can run is the command
    layer itself: `GMSession.execute_command` always dispatches through the
    GM's real, live `Client`, so every `mod_only(...)` decorator and other
    in-command permission check applies exactly as it would if the GM had
    typed the command in their AO client. A command name outside the
    listed groups (e.g. one added to a submodule's `__all__` after the
    cache was built) is executed exactly like a listed one; an
    unrecognized command name surfaces `commands.call`'s own
    "Invalid command: ..." message instead of a panel-side rejection.
    """

    _COMMAND_NAME_RE = re.compile(r"^[a-z0-9_]+$")

    _DOCS_URL = "https://github.com/Crystalwarrior/KFO-Server/blob/master/docs/commands.md"

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    async def handle_list_commands(self, request):
        return web.json_response({
            "ok": True,
            "groups": CommandLister.to_groups(),
            "docs_url": self._DOCS_URL,
        })

    async def handle_run_command(self, request):
        session = request["gm_session"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_request"}, status=400)

        cmd = str(data.get("cmd", "")).strip()
        if cmd.startswith("/"):
            cmd = cmd[1:]
        cmd = cmd.lower()
        arg = str(data.get("arg", ""))

        if not self._COMMAND_NAME_RE.match(cmd):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid command name."]}, status=400
            )

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
        # Recursive (like `HubDataRoutes.handle_charlist_get`'s file list),
        # so a charlist saved under a subfolder (via the Hub Data tab's
        # "save as" or the generic data-file upload API) is discoverable
        # here too -- both endpoints read the same `storage/charlists`
        # directory and `/charlist <name>` (the command behind "Apply")
        # never strips "/" from its argument, so a subpath name applies
        # exactly like a top-level one.
        return web.json_response({
            "charlists": _walk_data_files(DATA_KIND_DIRS["charlists"])
        })

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
        # Recursive, for the same reason as `handle_list_charlists` above --
        # this reads the same `storage/character_data` directory the Hub
        # Data tab's generic file API (also recursive) already exposes.
        return web.json_response({
            "snapshots": _walk_data_files(DATA_KIND_DIRS["character_data"])
        })

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


class HubDataRoutes:
    """
    Hub Data tab (A3/A4/A5/A6): hub save/load, the generic import/export
    file API shared by all five GM-facing yaml kinds, the charlist editor,
    and the music yaml editor.

    Every endpoint here re-checks `_hub_data_gate_ok` live (see its
    docstring) in addition to whatever gate the underlying command already
    enforces -- for the two listing/read endpoints that have no command
    behind them at all (`GET .../saves`, `GET .../files`, `GET .../file`),
    this panel-side check is the ONLY gate, so it is not optional.

    Command bodies this class routes through, and what was verified about
    each by reading `server/commands/hubs.py`, `server/commands/music.py`,
    and `server/commands/character.py` directly:

    - `save_hub`/`load_hub` (hubs.py:102/168, `@mod_only(hub_owners=True)`):
      write/read `storage/hubs/<name>.yaml` or `storage/hubs/read_only/<name>.yaml`;
      `save_hub`'s argument is `shlex.split`, so a name containing spaces
      must be quoted; `load_hub`'s is NOT `shlex.split` (the raw arg text is
      used as the filename verbatim), so it must be passed unquoted.
    - `charlist` (character.py:1424, `@mod_only(hub_owners=True)`) ->
      `AreaManager.load_characters` (area_manager.py:185), which
      LOWERCASES its argument before opening
      `storage/charlists/<arg>.yaml` -- so any charlist this class writes
      to disk for later loading through this command is saved under its
      lowercased name, or `/charlist`/this tab's own "Apply" would never
      find it again on a case-sensitive filesystem.
    - `hub_musiclist` (music.py:338, `@mod_only(hub_owners=True)`) is the
      command that actually sets `AreaManager.music_ref`/`music_list` --
      i.e. the HUB's musiclist. `musiclist` (music.py:286, no decorator)
      sets the *client's own local* musiclist instead
      (`client.music_list`/`client.music_ref`); despite the similar name it
      is the wrong command for this tab and is deliberately not used here.

    Subfolders: every name this class accepts (hub save/load, the generic
    `kind`/`name` file API, charlist `save_as`) may now be a multi-segment
    "/"-separated subpath (`_split_data_name`, 1-4 segments, no `read_only`
    segment) addressing a file nested inside its kind's directory. Listing
    (`_list_data_files`/`_walk_data_files`) recurses to find them (skipping
    any `read_only` directory at any depth); each kind's own `read_only/`
    tree stays flat/top-level, exactly as before. `save_hub`/`load_hub`
    themselves strip every "/" from their own argument
    (`derelative(arg).replace('/', '')`), so subpath saves/loads for hubs
    specifically are staged through a throwaway top-level temp file (see
    `handle_hub_save`/`handle_hub_load`) rather than passed to the command
    directly; `charlist`/`hub_musiclist` never strip "/" from their
    argument, so their subpath names pass straight through unchanged.
    """

    def __init__(self, session_manager, server, bridge=None):
        self._session_manager = session_manager
        self._server = server
        self._bridge = bridge

    def _push_areas_changed(self, session):
        if self._bridge is None:
            return
        try:
            hub_id = session.current_hub().id
        except Exception:
            return
        self._bridge.push_areas_changed(hub_id)

    def _require_session_and_gate(self, request):
        """
        Shared prefix for every handler below: pull the session out of the
        request, re-validate it, and re-check `_hub_data_gate_ok` live.
        Returns `(session, None)` on success or `(None, error_response)`.
        """
        session = request["gm_session"]
        if not session.is_valid():
            return None, web.json_response({"error": "session_invalid"}, status=401)
        if not _hub_data_gate_ok(session):
            return None, web.json_response(
                {"ok": False, "output": ["[ERROR] You must be authorized to do that."],
                 "error": "not_authorized"},
                status=403,
            )
        return session, None

    # -- A3: hub save/load ------------------------------------------------

    async def handle_hub_saves(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        return web.json_response({"ok": True, "files": _list_data_files("hubs")})

    async def handle_hub_save(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400)
        name = str(data.get("name", "")).strip()
        segments = _split_data_name(name)
        if segments is None:
            # A blank (or otherwise malformed) argument to `ooc_cmd_save_hub`
            # is NOT "save this hub under no name" -- for a mod-bound session
            # it dumps EVERY hub on the server to `config/areas_new.yaml`.
            # This endpoint is a scoped "save this one hub" action, so
            # anything that isn't a well-formed data-file name (same
            # allowlist every other `/api/gm/data/...`/`/api/gm/hub/...`
            # file name is validated against) must be rejected here rather
            # than silently forwarded into the far more destructive global
            # variant.
            return web.json_response({"ok": False, "error": "invalid_name"}, status=400)

        if len(segments) == 1:
            # `ooc_cmd_save_hub` runs its argument through `shlex.split` --
            # quote so a name containing spaces survives as one token
            # instead of being split apart (and so args[1:] doesn't get
            # misread as the "read_only" flag).
            try:
                output = session.execute_command("save_hub", shlex.quote(name))
            except SessionInvalid:
                return web.json_response({"error": "session_invalid"}, status=401)
            return _command_response(output)

        # Multi-segment (subfolder) name: `ooc_cmd_save_hub` itself does
        # `derelative(arg).replace('/', '')` on its filename argument, so it
        # can never be made to write into a subfolder directly. Save under a
        # throwaway top-level temp name through the real command instead
        # (exercising the exact same save/permission path as a normal save),
        # then move the produced file into the validated subpath.
        temp_name = uuid.uuid4().hex
        temp_path = os.path.join(DATA_KIND_DIRS["hubs"], f"{temp_name}.yaml")
        try:
            output = session.execute_command("save_hub", shlex.quote(temp_name))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not _command_ok(output):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return _command_response(output)

        dest_path, path_err = _safe_data_write_path("hubs", name)
        if dest_path is None:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return web.json_response({"ok": False, "error": path_err or "invalid_name"}, status=400)
        try:
            os.replace(temp_path, dest_path)
        except OSError as ex:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] Failed to move saved hub: {ex}"]}, status=500
            )
        return _command_response(output)

    async def handle_hub_load(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400)
        name = str(data.get("name", "")).strip()
        segments = _split_data_name(name)
        if segments is None:
            # A blank (or otherwise malformed) argument to `ooc_cmd_load_hub`
            # is NOT "load nothing" -- for a mod-bound session it calls
            # `hub_manager.load()`, which reloads/resets EVERY hub on the
            # server from `areas.yaml`, discarding all hubs' live state.
            # This endpoint is a scoped "load this one hub" action, so
            # anything that isn't a well-formed data-file name (same
            # allowlist every other `/api/gm/data/...`/`/api/gm/hub/...`
            # file name is validated against) must be rejected here rather
            # than silently forwarded into the far more destructive global
            # variant.
            return web.json_response({"ok": False, "error": "invalid_name"}, status=400)

        if len(segments) == 1:
            try:
                # `ooc_cmd_load_hub` uses its raw argument text verbatim as
                # the filename (no `shlex.split`) -- pass it through
                # unquoted.
                output = session.execute_command("load_hub", name)
            except SessionInvalid:
                return web.json_response({"error": "session_invalid"}, status=401)
            if _command_ok(output):
                self._push_areas_changed(session)
            return _command_response(output)

        # Multi-segment (subfolder) name: `ooc_cmd_load_hub` also strips
        # every "/" from its argument, so it can never read a subfolder
        # file directly. Resolve+validate the subfolder file ourselves,
        # stage a copy under a throwaway top-level temp name, and run the
        # real command against that temp name so every permission check and
        # side effect (`area_manager.load`, ARUP, music refresh) still goes
        # through the exact same code path as a normal load.
        src_path = _resolve_existing_data_path("hubs", name)
        if src_path is None:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        temp_name = uuid.uuid4().hex
        temp_path = os.path.join(DATA_KIND_DIRS["hubs"], f"{temp_name}.yaml")
        try:
            shutil.copyfile(src_path, temp_path)
        except OSError as ex:
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] Failed to stage hub for loading: {ex}"]}, status=500
            )
        try:
            output = session.execute_command("load_hub", temp_name)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        if _command_ok(output):
            self._push_areas_changed(session)
        return _command_response(output)

    # -- A4: generic yaml file API -----------------------------------------

    async def handle_data_files(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        kind = request.match_info.get("kind", "")
        files = _list_data_files(kind)
        if files is None:
            return web.json_response({"ok": False, "error": "unknown_kind"}, status=400)
        return web.json_response({"ok": True, "files": files})

    async def handle_data_file_get(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        kind = request.match_info.get("kind", "")
        if kind not in DATA_KIND_DIRS:
            return web.json_response({"ok": False, "error": "unknown_kind"}, status=400)
        name = request.query.get("name", "")
        path = _resolve_existing_data_path(kind, name)
        if path is None:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return web.json_response({"ok": False, "error": "read_failed"}, status=500)
        return web.json_response({"ok": True, "name": name, "content": content})

    async def handle_data_file_put(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        kind = request.match_info.get("kind", "")
        if kind not in DATA_KIND_DIRS:
            return web.json_response({"ok": False, "error": "unknown_kind"}, status=400)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        name = str(data.get("name", ""))
        content = data.get("content", "")
        if not isinstance(content, str):
            return web.json_response({"ok": False, "error": "invalid_content"}, status=400)
        if len(content.encode("utf-8")) > _MAX_DATA_FILE_BYTES:
            return web.json_response({"ok": False, "error": "file_too_large"}, status=400)
        try:
            _bounded_safe_load(content)
        except yaml.YAMLError as ex:
            return web.json_response({"ok": False, "error": f"invalid_yaml: {ex}"}, status=400)

        path, path_err = _safe_data_write_path(kind, name)
        if path is None:
            return web.json_response({"ok": False, "error": path_err or "invalid_name"}, status=400)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as ex:
            return web.json_response({"ok": False, "error": f"write_failed: {ex}"}, status=500)
        return web.json_response({"ok": True, "kind": kind, "name": name})

    # -- A4: generic per-kind "load into the hub" --------------------------

    async def handle_data_file_load(self, request):
        """
        POST /api/gm/data/{kind}/load -- apply a saved yaml file to the
        live hub, per kind (the "Load" button beside every "Download" in
        the Files subtab):

        - `charlists` -> `/charlist <name>` (`AreaManager.load_characters`
          LOWERCASES its argument, so the name is lowercased here first --
          otherwise a mixed-case name this browser lists could never be
          found again on a case-sensitive filesystem).
        - `musiclists` -> `/hub_musiclist <name>` (sets the HUB's music
          list, unlike `/musiclist` which only touches the client's).
        - `character_data` -> `/load_character_data <name>`.
        - `evidence` -> `/evidence_load <name>` into the GM's current area
          (same semantics as the Evidence tab's Load-pack button;
          `/evidence_overlay` when `overlay` is true).

        Existence is re-checked via `_resolve_existing_data_path` (after
        any lowercasing) so a GM gets a clear message instead of a bare
        command error. Every command body still runs through the real
        command layer with its own `@mod_only(...)` gate, and this route
        re-checks `_hub_data_gate_ok` on top of that.
        """
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        kind = request.match_info.get("kind", "")
        if kind not in ("evidence", "character_data", "charlists", "musiclists"):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] This yaml kind cannot be loaded."]}, status=400
            )
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        name = str(data.get("name", "")).strip()
        if kind == "charlists":
            # `load_characters` resolves against the lowercased name.
            name = name.lower()
        if _split_data_name(name) is None:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid file name."]}, status=400)
        if _resolve_existing_data_path(kind, name) is None:
            return web.json_response(
                {
                    "ok": False,
                    "output": [f"[ERROR] No file named '{name}' exists for yaml kind '{kind}'."],
                },
                status=404,
            )
        try:
            if kind == "charlists":
                output = session.execute_command("charlist", name)
            elif kind == "musiclists":
                output = session.execute_command("hub_musiclist", name)
            elif kind == "character_data":
                output = session.execute_command("load_character_data", name)
            else:  # evidence
                cmd = "evidence_overlay" if bool(data.get("overlay", False)) else "evidence_load"
                output = session.execute_command(cmd, derelative(name))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    # -- A5: charlist editor -------------------------------------------------

    async def handle_charlist_get(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        return web.json_response({
            "ok": True,
            "characters": list(hub.char_list),
            # Recursive (like `_list_data_files`'s editable side) so a
            # charlist previously saved under a subfolder name (see
            # `handle_charlist_submit`'s `save_as`) shows up here too.
            "files": _walk_data_files(DATA_KIND_DIRS["charlists"]),
        })

    async def handle_charlist_submit(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400)

        raw_characters = data.get("characters")
        if not isinstance(raw_characters, list) or not all(
            isinstance(c, str) for c in raw_characters
        ):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] 'characters' must be a list of strings."]},
                status=400,
            )
        characters = [c.strip() for c in raw_characters if c.strip() != ""]
        if not characters:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Character list must not be empty."]}, status=400
            )
        yaml_text = yaml.dump(characters, default_flow_style=False, allow_unicode=True)

        save_as = data.get("save_as")
        cleanup_path = None
        if save_as:
            # `AreaManager.load_characters` lowercases its argument before
            # opening the file -- save (and later apply) under the
            # lowercased name so `/charlist <save_as>` can find it again.
            # `str.lower()` on the whole string (rather than segment-by-
            # segment) is equivalent here since "/" itself has no case, and
            # -- unlike `ooc_cmd_save_hub`/`ooc_cmd_load_hub` --
            # `load_characters` never strips "/" from its argument, so a
            # multi-segment (subfolder) `save_as` name is written and
            # loaded from that subfolder directly, no temp-file staging
            # needed (see `_safe_data_write_path`, which now validates and
            # creates intermediate directories for such names).
            apply_name = str(save_as).strip().lower()
            if not apply_name:
                return web.json_response(
                    {"ok": False, "output": ["[ERROR] 'save_as' must not be blank."]}, status=400
                )
        else:
            apply_name = f"_gmtmp_{uuid.uuid4().hex[:16]}"

        path, path_err = _safe_data_write_path("charlists", apply_name)
        if path is None:
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] {path_err or 'invalid_name'}"]}, status=400
            )
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(yaml_text)
        except OSError as ex:
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] Failed to save charlist: {ex}"]}, status=500
            )
        if not save_as:
            cleanup_path = path

        hub = session.current_hub()
        if hub.char_list_ref == apply_name:
            # `AreaManager.load_characters()` no-ops (`if self.char_list_ref
            # == charlist: return`) whenever the requested name already
            # matches the hub's current ref -- which is exactly what
            # happens on a same-`save_as` resubmit (edit, Submit, edit
            # again, Submit again). Without this, the yaml on disk gets
            # rewritten above but the live `hub.char_list` is never
            # refreshed, while the command still reports success. Reset the
            # ref first so the reload below actually runs; `load_characters`
            # will set it right back to `apply_name` on success.
            hub.char_list_ref = ""

        try:
            # Same underlying mechanism/gate as `/charlist <name>` --
            # `ooc_cmd_charlist` only accepts a filename, so an unsaved
            # submit is staged through a throwaway scratch file (cleaned up
            # below) rather than saved permanently.
            output = session.execute_command("charlist", apply_name)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        finally:
            if cleanup_path is not None:
                try:
                    os.remove(cleanup_path)
                except OSError:
                    pass

        if _command_ok(output):
            self._push_areas_changed(session)
        return _command_response(output)

    # -- A6: music yaml editor -----------------------------------------------

    async def handle_music_get(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        music_ref = hub.music_ref or ""

        content = None
        if music_ref and music_ref != "unsaved":
            path = _resolve_existing_data_path("musiclists", music_ref)
            if path is not None:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                except OSError:
                    content = None
        if content is None:
            # No (valid, on-disk) ref -- serialize the live in-memory list
            # the same way `/musiclist_save` writes it to disk.
            content = yaml.dump(hub.music_list, default_flow_style=False, allow_unicode=True)

        return web.json_response({"ok": True, "music_ref": music_ref, "content": content})

    async def handle_music_apply(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400)
        name = str(data.get("name", ""))
        try:
            # See class docstring: `hub_musiclist`, NOT `musiclist`, is the
            # command that sets the HUB's musiclist.
            output = session.execute_command("hub_musiclist", name)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)


class EvidenceRoutes:
    """
    Evidence tab (formerly "Demos"): CRUD over an area's evidence items --
    each item's `desc` field doubles as a demo script -- plus the
    run/stop/status/eval endpoints that drive the real `/demo` command.
    User-facing vocabulary is "evidence" throughout; the demo-script
    coupling is an internal implementation detail explained inline.
    """

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    def _get_area(self, session, area_id):
        hub = session.current_hub()
        if area_id < 0 or area_id >= len(hub.areas):
            return None
        return hub.areas[area_id]

    def _resolve(self, session, request):
        """Resolve `{area_id}/{evidence_id}` from the URL, or an error response."""
        try:
            area_id = int(request.match_info["area_id"])
            evidence_id = int(request.match_info["evidence_id"])
        except (KeyError, ValueError):
            return None, None, web.json_response({"error": "invalid_id"}, status=400)
        area = self._get_area(session, area_id)
        if area is None:
            return None, None, web.json_response({"error": "area_not_found"}, status=404)
        if evidence_id < 0 or evidence_id >= len(area.evi_list.evidences):
            return None, None, web.json_response({"error": "evidence_not_found"}, status=404)
        return area, evidence_id, None

    async def handle_list_evidence(self, request):
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

        evidence = [EvidenceSerializer.to_list_item(i, evi, area) for i, evi in enumerate(area.evi_list.evidences)]
        return web.json_response({"area_id": area.id, "area_name": area.name, "evidence": evidence})

    async def handle_get_evidence(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        area, evidence_id, err = self._resolve(session, request)
        if err is not None:
            return err
        evi = area.evi_list.evidences[evidence_id]
        return web.json_response(EvidenceSerializer.to_detail(evidence_id, evi, area))

    async def handle_put_evidence(self, request):
        session = request["gm_session"]
        area, evidence_id, err = self._resolve(session, request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        name = str(data.get("name", "*"))
        desc = str(data.get("desc", "*"))
        image = str(data.get("image", "*"))
        props = data.get("props")
        try:
            ok = session.edit_evidence_direct(area, evidence_id, name, desc, image)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not ok:
            return web.json_response({"ok": False, "error": "not_authorized_or_invalid"}, status=403)
        if props is not None:
            try:
                props_ok = session.set_evidence_props_direct(area, evidence_id, props)
            except SessionInvalid:
                return web.json_response({"error": "session_invalid"}, status=401)
            if not props_ok:
                return web.json_response({"ok": False, "error": "invalid_props"}, status=400)
        return web.json_response({"ok": True})

    async def handle_new_evidence(self, request):
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
        props = data.get("props")
        try:
            ok = session.add_evidence_direct(area, name, desc, image)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not ok:
            return web.json_response({"ok": False, "error": "not_authorized_or_invalid"}, status=403)
        # `add_evidence` always appends, so the new entry's id is the last
        # index. The frontend Evidence tab uses this to immediately open
        # the evidence item it just created.
        new_id = len(area.evi_list.evidences) - 1
        if props is not None:
            try:
                props_ok = session.set_evidence_props_direct(area, new_id, props)
            except SessionInvalid:
                return web.json_response({"error": "session_invalid"}, status=401)
            if not props_ok:
                return web.json_response({"ok": False, "error": "invalid_props"}, status=400)
        return web.json_response({"ok": True, "id": new_id})

    async def handle_delete_evidence(self, request):
        session = request["gm_session"]
        area, evidence_id, err = self._resolve(session, request)
        if err is not None:
            return err
        try:
            ok = session.del_evidence_direct(area, evidence_id)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if not ok:
            return web.json_response({"ok": False, "error": "not_authorized_or_invalid"}, status=403)
        return web.json_response({"ok": True})

    async def handle_run_evidence(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
            evidence_id = int(request.match_info["evidence_id"])
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
            output = session.execute_command("demo", str(evidence_id + 1))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        ok = _command_ok(output)
        if ok and area.demo_runner is not None:
            # Dynamic attribute stamp (mirrors the `_gm_bind_key` pattern) so
            # the panel can report which evidence entry is currently running
            # -- `ScriptRunner` itself has no notion of "which evidence".
            area.demo_runner.gm_panel_demo_id = evidence_id
        return web.json_response({"ok": ok, "output": output})

    async def handle_stop_evidence(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        # `ooc_cmd_stop_demo` always operates on `client.area` -- see the
        # comment in handle_run_evidence.
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

    async def handle_stop_all_evidence(self, request):
        session = request["gm_session"]
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        # Hub-wide stop still only makes sense relative to the GM's live
        # current area/hub -- same reasoning as handle_stop_evidence.
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


class AssetRoutes:
    """
    A6: exposes the server's static-asset resolution config so the frontend
    (`GMLocalContent`, Package C) can fall back to server-hosted assets
    (backgrounds, char icons, evidence images) when no local base
    folder/URL is configured or an item is missing from it.
    """

    def __init__(self, server, config):
        self._server = server
        self._config = config

    async def handle_config(self, request):
        server_config = getattr(self._server, "config", None) or {}
        asset_url = str(server_config.get("asset_url", "") or "")
        bg_thumb_base = str(self._config.get("background_thumb_base_url", "") or "")
        return web.json_response({
            "ok": True, "asset_url": asset_url, "bg_thumb_base": bg_thumb_base,
        })


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
        area_routes = AreaRoutes(self._session_manager, self._server, self._config, self.bridge)
        client_routes = ClientRoutes(self._session_manager, self._server)
        command_routes = CommandRoutes(self._session_manager, self._server)
        character_routes = CharacterRoutes(self._session_manager, self._server)
        hub_data_routes = HubDataRoutes(self._session_manager, self._server, self.bridge)
        evidence_routes = EvidenceRoutes(self._session_manager, self._server)
        asset_routes = AssetRoutes(self._server, self._config)

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

        # Areas tab -- literal/collection routes ("hub/areas/...") registered
        # separately from the per-area "{area_id}/..." routes; none of these
        # collide since aiohttp matches on full path shape.
        app.router.add_get("/api/gm/areas", require(area_routes.handle_list_areas))
        app.router.add_get(
            "/api/gm/areas/background_thumb_base_url",
            require(area_routes.handle_background_thumb_base_url),
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/background", require(area_routes.handle_set_background)
        )
        app.router.add_get(
            "/api/gm/areas/{area_id}/detail", require(area_routes.handle_area_detail)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/pref", require(area_routes.handle_set_pref)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/edit", require(area_routes.handle_edit_area)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/links/add", require(area_routes.handle_link_add)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/links/remove", require(area_routes.handle_link_remove)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/links/set", require(area_routes.handle_link_set)
        )

        # Hub-level area management (create/remove/swap) -- distinct prefix
        # from the per-area routes above since these act on the whole hub.
        app.router.add_post(
            "/api/gm/hub/areas/create", require(area_routes.handle_create_area)
        )
        app.router.add_post(
            "/api/gm/hub/areas/swap", require(area_routes.handle_swap_areas)
        )
        app.router.add_post(
            "/api/gm/hub/areas/{area_id}/remove", require(area_routes.handle_remove_area)
        )

        # Shared local-content resolution config (Package C's GMLocalContent).
        app.router.add_get("/api/gm/assets/config", require(asset_routes.handle_config))

        # Clients tab
        app.router.add_get("/api/gm/clients", require(client_routes.handle_list_clients))
        app.router.add_post(
            "/api/gm/clients/{client_id}/gm", require(client_routes.handle_promote)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/ungm", require(client_routes.handle_demote)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/pm", require(client_routes.handle_pm)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/area", require(client_routes.handle_teleport_to_area)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/teleport_here",
            require(client_routes.handle_teleport_here),
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

        # Hub Data tab -- hub save/load, generic yaml import/export for all
        # five GM-facing data kinds, the charlist editor, the music editor.
        app.router.add_get("/api/gm/hub/saves", require(hub_data_routes.handle_hub_saves))
        app.router.add_post("/api/gm/hub/save", require(hub_data_routes.handle_hub_save))
        app.router.add_post("/api/gm/hub/load", require(hub_data_routes.handle_hub_load))

        # Literal routes ("data/{kind}/files") registered before the
        # dynamic "data/{kind}/file" route to mirror the Evidence tab's
        # ordering convention below -- these don't actually collide (aiohttp
        # matches on full path shape) but keeping the convention consistent
        # makes the route table easier to scan.
        app.router.add_get(
            "/api/gm/data/{kind}/files", require(hub_data_routes.handle_data_files)
        )
        app.router.add_get("/api/gm/data/{kind}/file", require(hub_data_routes.handle_data_file_get))
        app.router.add_put("/api/gm/data/{kind}/file", require(hub_data_routes.handle_data_file_put))
        app.router.add_post("/api/gm/data/{kind}/load", require(hub_data_routes.handle_data_file_load))

        app.router.add_get("/api/gm/charlist", require(hub_data_routes.handle_charlist_get))
        app.router.add_post(
            "/api/gm/charlist/submit", require(hub_data_routes.handle_charlist_submit)
        )

        app.router.add_get("/api/gm/music", require(hub_data_routes.handle_music_get))
        app.router.add_post("/api/gm/music/apply", require(hub_data_routes.handle_music_apply))

        # Evidence tab (formerly "Demos") -- literal routes registered
        # before the dynamic {evidence_id} route so e.g. "status" isn't
        # swallowed as an evidence id.
        app.router.add_get("/api/gm/evidence", require(evidence_routes.handle_list_evidence))
        app.router.add_post("/api/gm/evidence/eval", require(evidence_routes.handle_eval))
        app.router.add_get("/api/gm/evidence_packs", require(evidence_routes.handle_list_packs))
        app.router.add_post(
            "/api/gm/evidence_packs/save", require(evidence_routes.handle_save_pack)
        )
        app.router.add_post(
            "/api/gm/evidence_packs/{name}/load", require(evidence_routes.handle_load_pack)
        )
        app.router.add_get(
            "/api/gm/evidence/{area_id}/status", require(evidence_routes.handle_status)
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/new", require(evidence_routes.handle_new_evidence)
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/stop_all",
            require(evidence_routes.handle_stop_all_evidence),
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/stop", require(evidence_routes.handle_stop_evidence)
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/{evidence_id}/run",
            require(evidence_routes.handle_run_evidence),
        )
        app.router.add_get(
            "/api/gm/evidence/{area_id}/{evidence_id}", require(evidence_routes.handle_get_evidence)
        )
        app.router.add_put(
            "/api/gm/evidence/{area_id}/{evidence_id}", require(evidence_routes.handle_put_evidence)
        )
        app.router.add_delete(
            "/api/gm/evidence/{area_id}/{evidence_id}",
            require(evidence_routes.handle_delete_evidence),
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
