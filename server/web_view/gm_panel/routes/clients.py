"""Clients tab routes: roster, GM promote/demote, PM, teleport."""

from aiohttp import web

from server.constants import _SYSTEM_IPID
from server.remote_client import RemoteClient

from server.web_view.gm_panel.serializers import ClientSerializer
from server.web_view.gm_panel.sessions import SessionInvalid
from server.web_view.gm_panel.storage import _command_response


class ClientRoutes:
    """
    Clients tab: roster, GM promote/demote, and per-player management actions
    (private message, teleport).

    Every management action below dispatches through the real command layer via
    `execute_command` -- `/pm` (messaging.py) and `/area_kick` (areas.py,
    `@mod_only(area_owners=True)`, which a hub-owner passes via
    `Area.owners = area_manager.owners | _owners` and a mod passes via `is_mod`)
    -- so the exact same permission checks and side effects run as if the GM had
    typed the command in their AO client.
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
        # `/pm <id> <message>` -- the id is scoped to the GM's current hub by
        # `get_targets`'s default (non-`all_hub`) search, matching the roster
        # this tab displays.
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
        # `/area_kick <id> <destination> [target_pos]` -- the command's own gate
        # (`@mod_only(area_owners=True)`) and its "can't kick to an area you
        # don't own as a CM" check both apply as if the GM had typed it, and the
        # destination id resolves against the GM's hub.
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
            # `/area_kick <id>` with no destination defaults the target to the
            # GM's own current area -- i.e. "teleport to me"/arrive.
            output = session.execute_command("area_kick", str(client_id))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)
