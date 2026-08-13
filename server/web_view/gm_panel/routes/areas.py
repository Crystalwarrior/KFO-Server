"""Areas tab routes: graph snapshot, inspector, area CRUD, and link management."""

from aiohttp import web

from server.exceptions import AreaError
from server.schema.area_fields import AREA_WRITE_STRATEGIES
from server.schema.link_props import LINK_PROPERTY_SCHEMA

from server.web_view.gm_panel.serializers import AreaDetailSerializer, AreaSerializer
from server.web_view.gm_panel.sessions import SessionInvalid
from server.web_view.gm_panel.storage import _command_ok, _command_response


class AreaRoutes:
    """
    Areas tab: hub graph snapshot, per-area inspector (detail/prefs/edit),
    hub-level area management (create/remove/swap), and link management.
    """

    # Derived from server/schema/link_props.py: frontend `data-prop` -> (on, off)
    # command pair, for the generic `input[data-prop]` bool-toggle handler. A new
    # boolean link property (with a `bool_cmds` pair) is added automatically.
    _LINK_BOOL_PROPS = {
        prop.prop: prop.bool_cmds
        for prop in LINK_PROPERTY_SCHEMA
        if prop.bool_cmds is not None
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
            # The suffix rides along in the same request (the inspector's
            # "suffix | background / overlay" form) -- run the real
            # `/bg_suffix` on the target area when the caller supplied one.
            # It is only sent when present, so older clients that POST
            # without a `suffix` key leave the current suffix untouched.
            if _command_ok(output) and "suffix" in data:
                area = self._area_from_request(session, request)
                if area is not None:
                    suffix_out = session.execute_command_in_area(
                        area, "bg_suffix", str(data.get("suffix", ""))
                    )
                    output = output + suffix_out
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        if _command_ok(output):
            self._push_areas_changed(session)
        return _command_response(output)

    async def handle_background_thumb_base_url(self, request):
        base_url = self._config.get("background_thumb_base_url", "")
        return web.json_response({"base_url": base_url})

    # -- area detail + editing ----------------------------------------

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
            return web.json_response({"error": "area_not_found"}, status=404)
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )
        pref = str(data.get("pref", "")).strip()
        value = bool(data.get("value", False))

        # `ooc_cmd_area_pref` does `getattr(client.area, cmd)` with no default
        # and only catches `ValueError`/`AreaError`/`ClientError` -- an unknown
        # attribute name would raise a bare `AttributeError` straight through
        # `execute_command_in_area`. Verify it's a real, currently-boolean
        # attribute ourselves first so a bad `pref` comes back as a clean 400
        # instead of a 500.
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
        trigger = str(data.get("trigger", "")).strip()

        # The field -> write dispatch lives once in `server/schema/area_fields.py`
        # (`AREA_WRITE_STRATEGIES`); a new editable field is a single registry
        # entry there, and this handler + the inspector pick it up automatically.
        strategy = AREA_WRITE_STRATEGIES.get(field)
        if strategy is None:
            return web.json_response(
                {"ok": False, "output": [f"[ERROR] Unsupported field: {field}"]}, status=400
            )

        extra = {"trigger": trigger}
        try:
            output = strategy(session, area, value, extra)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)

        if _command_ok(output):
            self._push_areas_changed(session)
        return _command_response(output)

    # -- hub-level area management -----------------------------------

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
        new_area_id = len(hub.areas) - 1
        if insert_at is not None:
            try:
                target = int(insert_at)
            except (TypeError, ValueError):
                target = None
            if target is not None:
                idx = new_area_id
                target = max(0, min(target, idx))
                while idx > target:
                    swap_output = session.execute_command("area_swap", f"{idx} {idx - 1}")
                    output = output + swap_output
                    if not _command_ok(swap_output):
                        break
                    idx -= 1
                new_area_id = idx

        self._push_areas_changed(session)
        return web.json_response({
            "ok": True, "output": output,
            "area_id": new_area_id,
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

    async def handle_switch_areas(self, request):
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
            # `/area_switch` swaps two areas WITHOUT correcting links --
            # deliberately distinct from `/area_swap` (the "Swap" button).
            output = session.execute_command("area_switch", f"{a} {b}")
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)

        hub = session.current_hub()
        if _command_ok(output):
            self._push_areas_changed(session)
        return web.json_response({
            "ok": _command_ok(output), "output": output,
            "hub_id": hub.id, "hub_name": hub.name, "areas": self._areas_snapshot(hub),
        })

    async def handle_duplicate_area(self, request):
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
            output = session.execute_command("area_duplicate", str(area_id))
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)

        hub = session.current_hub()
        if _command_ok(output):
            self._push_areas_changed(session)
        return web.json_response({
            "ok": _command_ok(output), "output": output,
            "hub_id": hub.id, "hub_name": hub.name, "areas": self._areas_snapshot(hub),
        })

    # -- link management ---------------------------------------------

    async def _resolve_link_request(self, request):
        """
        Shared prefix for every `/links/*` endpoint: pull the session and source
        area out of the request, parse the JSON body, and parse `target_id`.
        Returns `(session, area, data, target_id, None)` on success, or
        `(None, None, None, None, error_response)` on failure.
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
        Shared body for the two-way `/links/*` endpoints: resolve the source
        area, parse `target_id`, run `cmd` through `execute_command_in_area`,
        and return the updated link list.
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
        The `two_way=false` path for `/links/add|remove` -- performs the one-way
        `Area.link()`/`Area.unlink()` primitive directly on `area` (never
        touching the target area's own link dict), bypassing `commands.call`
        entirely.

        The permission gate below replicates `/unlink`'s exactly: the source area
        and the target area must each be owned (mod or owner).
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
                # `value` is a list of 0-indexed evidence ids; `/link_evidence`
                # itself is 1-indexed on the wire, so translate here rather than
                # exposing that command-layer quirk to the frontend.
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





