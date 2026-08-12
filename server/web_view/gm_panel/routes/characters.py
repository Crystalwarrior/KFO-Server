"""Characters tab routes: char list slots, charlists, and Character Data CRUD."""

from aiohttp import web

from server.web_view.gm_panel.serializers import CharacterDataSerializer, CharacterSlotSerializer
from server.web_view.gm_panel.sessions import SessionInvalid
from server.web_view.gm_panel.storage import DATA_KIND_DIRS, _command_response, _walk_data_files


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
        # Recursive (like `HubDataRoutes.handle_charlist_get`'s file list), so a
        # charlist saved under a subfolder is discoverable here too.
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
        # this reads the same `storage/character_data` directory the Hub Data
        # tab's generic file API (also recursive) already exposes.
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
