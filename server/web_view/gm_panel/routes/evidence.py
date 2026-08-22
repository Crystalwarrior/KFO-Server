"""Evidence tab routes: CRUD over evidence items (each `desc` is a demo script)."""

from aiohttp import web

from server.constants import derelative
from server.scripting import live_get, live_sources, resolve_value, ScriptingError

from server.web_view.gm_panel.serializers import CharacterDataSerializer, EvidenceSerializer
from server.web_view.gm_panel.sessions import SessionInvalid
from server.web_view.gm_panel.storage import _command_ok, _command_response, _list_yaml_names


class EvidenceRoutes:
    """
    Evidence tab (formerly "Demos"): CRUD over an area's evidence items -- each
    item's `desc` field doubles as a demo script -- plus the run/stop/status/eval
    endpoints that drive the real `/demo` command. User-facing vocabulary is
    "evidence" throughout; the demo-script coupling is an internal detail.
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
        # `add_evidence` always appends, so the new entry's id is the last index.
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
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        area, evidence_id, err = self._resolve(session, request)
        if err is not None:
            return err
        # `ooc_cmd_demo` reads its target area off `client.area`, so shadow
        # `.area` to the picked area for the duration of this fully-synchronous
        # call. Playback itself is bound to the evidence's own area by
        # `Area.play_demo` regardless of where the GM is standing, so Run works
        # on any area of the hub.
        try:
            output = session.execute_command_in_area(area, "demo", str(evidence_id + 1))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        ok = _command_ok(output)
        if ok and area.demo_runner is not None:
            # Dynamic attribute stamp (mirrors the `_gm_bind_key` pattern) so the
            # panel can report which evidence entry is currently running --
            # `ScriptRunner` itself has no notion of "which evidence".
            area.demo_runner.gm_panel_demo_id = evidence_id
        return web.json_response({"ok": ok, "output": output})

    async def handle_stop_evidence(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        area = self._get_area(session, area_id)
        if area is None:
            return web.json_response({"ok": False, "output": ["[ERROR] Area not found."]}, status=404)
        # Blank `/stop_demo` acts on `client.area`; shadow it to the picked area
        # so Stop stops playback there rather than wherever the GM is standing.
        try:
            output = session.execute_command_in_area(area, "stop_demo", "")
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)

    async def handle_stop_all_evidence(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        try:
            area_id = int(request.match_info["area_id"])
        except ValueError:
            return web.json_response({"ok": False, "output": ["[ERROR] Invalid area id."]}, status=400)
        # Validate the id for API consistency, but `/stop_demo all` sweeps every
        # area of the hub no matter where it's called from -- no current-area
        # coupling at all.
        area = self._get_area(session, area_id)
        if area is None:
            return web.json_response({"ok": False, "output": ["[ERROR] Area not found."]}, status=404)
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



