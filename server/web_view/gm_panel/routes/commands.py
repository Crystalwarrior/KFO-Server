"""Commands tab routes: auto-generated command list + free-form runner."""

import re

from aiohttp import web

from server.exceptions import AreaError, ClientError

from server.web_view.gm_panel.commands_meta import CommandLister
from server.web_view.gm_panel.sessions import SessionInvalid
from server.web_view.gm_panel.storage import _command_response


class CommandRoutes:
    """
    Commands tab: the auto-generated command list (`CommandLister`, not a
    whitelist) + the free-form command runner.

    `CommandLister` is UX curation only -- it is not consulted to decide what a
    GM can run. The *only* gate on what a GM can run is the command layer
    itself: `GMSession.execute_command` always dispatches through the GM's real,
    live `Client`, so every `mod_only(...)` decorator and other in-command
    permission check applies exactly as it would if the GM had typed the command
    in their AO client.
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

    async def handle_set_monitor(self, request):
        """Toggle OOC or IC monitoring for this session (GMs and admins alike).

        The monitor is session-level state that lives on `GMSession`/`RemoteSession`;
        its frames stream over the shared `/ws/gm/live` as
        ``{"type": "monitor_ooc"|"monitor_ic", "data": {...}}``. Being de-gated here
        (any valid session) is deliberate -- the feature is a console aid, not an
        admin privilege.
        """
        session = request["gm_session"]
        kind = request.match_info["kind"]
        if kind not in ("ooc", "ic"):
            return web.json_response({"error": "invalid monitor kind"}, status=400)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        enabled = bool(data.get("enabled", False))
        try:
            session.set_monitor(kind, enabled)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        area = session.current_area()
        return web.json_response({
            "ok": True,
            "monitoring": enabled,
            "area_name": area.name if area is not None else "?",
            "area_id": area.id if area is not None else -1,
        })

    async def handle_get_scope(self, request):
        """Return the console's travel scope for this session.

        GMs (hub-bound) get ``can_travel: false`` plus their own hub; admins get
        ``can_travel: true`` plus the full list of hubs they may travel to. The
        Commands tab uses this to render either a fixed "bound to <hub>" label or
        an admin-only hub selector.
        """
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        payload = {
            "ok": True,
            "role": session.role,
            "can_travel": session.can_travel,
            "current_hub_id": hub.id,
            "current_hub_name": hub.name,
            "hubs": [],
        }
        if session.can_travel:
            payload["hubs"] = [
                {"id": h.id, "name": h.name} for h in session.available_hubs()
            ]
        return web.json_response(payload)

    async def handle_travel(self, request):
        """Move an admin session to another hub (the polymorphic ``can_travel``
        capability). Hub-bound GM sessions are rejected with a 403."""
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        if not session.can_travel:
            return web.json_response({"error": "not_authorized"}, status=403)
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "error": "invalid_request"}, status=400
            )
        try:
            hub_id = int(data.get("hub_id"))
        except (TypeError, ValueError):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid hub id."]}, status=400
            )
        try:
            hub = session.travel_to_hub(hub_id)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        except (ClientError, AreaError) as ex:
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] {ex}"]}, status=400
            )
        session.push_event("hub_switched", {
            "new_hub_id": hub.id,
            "new_hub_name": hub.name,
        })
        return web.json_response({"ok": True, "hub_id": hub.id, "hub_name": hub.name})
