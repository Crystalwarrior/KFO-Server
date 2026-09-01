"""Demos tab routes: the demo-scripting language surface.

This module is the scripting side of the panel, deliberately separate from
`routes/evidence.py`: today a demo script is stored inside an evidence item's
`desc` (the only storage that has ever existed), but evidence and demo
scripting are meant to be separated eventually, so the scripting API lives
under its own `/api/gm/demos/*` prefix from day one. The single route here
parses arbitrary script text with the authoritative server parser; run/stop/
status still go through the evidence endpoints until scripts get their own
backend.
"""

from aiohttp import web

from server.script_runner import parse_demo_description
from server.scripting import live_path_menu

from server.web_view.gm_panel.serializers import EvidenceSerializer


class DemosRoutes:
    """Routes for the Demos tab (Text/Visual script editing)."""

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    def _get_area(self, session, area_id):
        hub = session.current_hub()
        if area_id < 0 or area_id >= len(hub.areas):
            return None
        return hub.areas[area_id]

    async def handle_parse(self, request):
        """Parse script text with the real demo parser and report warnings.

        Body: `{text, area_id?}`. Returns `{instructions, warnings}` where
        `instructions` is the exact instruction-tuple list the ScriptRunner
        would execute and `warnings` reuses the evidence serializer's
        out-of-range MS char-id check (needs an area, so `area_id` defaults to
        the GM's current area). The frontend uses this to rebuild a Blockly
        workspace from an arbitrary textarea edit -- the same authoritative
        grammar the server runs, never a JS re-implementation.
        """
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)

        text = str(data.get("text", ""))
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

        instructions = parse_demo_description(text)
        return web.json_response({
            "ok": True,
            "instructions": [list(instr) for instr in instructions],
            "warnings": EvidenceSerializer._out_of_range_warnings(area, instructions),
        })

    async def handle_live_paths(self, request):
        """List every live-state path the demo language can read.

        Generated from the scripting whitelists themselves
        (`scripting.live_path_menu`), so the get block's "insert variable"
        dropdown always matches exactly what the runner accepts - no
        hand-maintained mirror to drift out of sync. No area is needed: the
        field whitelists are server-wide (only the *values* are per-area).
        """
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        return web.json_response({"ok": True, "paths": list(live_path_menu())})
