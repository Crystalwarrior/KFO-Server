"""Hub Data tab routes: hub save/load, generic yaml file API, charlist/music editors."""

import os
import shlex
import shutil
import uuid

import oyaml as yaml

from aiohttp import web

from server.constants import derelative

from server.web_view.gm_panel.sessions import SessionInvalid
from server.web_view.gm_panel.storage import (
    DATA_KIND_DIRS,
    _MAX_DATA_FILE_BYTES,
    _command_ok,
    _command_response,
    _hub_data_gate_ok,
    _list_data_files,
    _public_data_files,
    _resolve_existing_data_path,
    _safe_data_write_path,
    _split_data_name,
    _walk_data_files,
)
from server.web_view.gm_panel.yaml_safety import _bounded_safe_load


class HubDataRoutes:
    """
    Hub Data tab: hub save/load, the generic import/export file API shared by all
    five GM-facing yaml kinds, the charlist editor, and the music yaml editor.

    Every endpoint here re-checks `_hub_data_gate_ok` live in addition to
    whatever gate the underlying command already enforces; for the read-only
    listing/read endpoints that have no command behind them, this panel-side
    check is the ONLY gate, so it is not optional.

    Command routing notes (verified against `server/commands/hubs.py`,
    `music.py`, `character.py`): `save_hub`/`load_hub` write/read
    `storage/hubs/<name>.yaml`; `charlist` LOWERCASES its argument; `hub_musiclist`
    (not `musiclist`) sets the HUB's musiclist.
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
        request, re-validate it, and re-check `_hub_data_gate_ok` live. Returns
        `(session, None)` on success or `(None, error_response)`.
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

    # -- hub save/load ------------------------------------------------

    async def handle_hub_saves(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        # Mods have server-wide scope and can safely see every hub on the
        # server, editable ones included. Non-mod hub GMs only get the public
        # read_only hubs; their own editable saves are merged back client-side
        # from localStorage (see DATA_KIND_LIST_PUBLIC_ONLY).
        if session.bound_client.is_mod:
            files = _list_data_files("hubs")
        else:
            files = _public_data_files("hubs")
        return web.json_response({"ok": True, "files": files})

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
            # A blank/malformed argument to `ooc_cmd_save_hub` is NOT "save this
            # hub under no name" -- for a mod-bound session it dumps EVERY hub to
            # `config/areas_new.yaml`. Reject it rather than forward into that.
            return web.json_response({"ok": False, "error": "invalid_name"}, status=400)

        if len(segments) == 1:
            # `ooc_cmd_save_hub` runs its argument through `shlex.split` -- quote
            # so a name containing spaces survives as one token.
            try:
                output = session.execute_command("save_hub", shlex.quote(name))
            except SessionInvalid:
                return web.json_response({"error": "session_invalid"}, status=401)
            return _command_response(output)

        # Multi-segment (subfolder) name: `ooc_cmd_save_hub` itself strips "/"
        # from its filename argument, so it can never write into a subfolder.
        # Save under a throwaway top-level temp name through the real command
        # (exercising the exact same save/permission path), then move the file
        # into the validated subpath.
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
            # A blank/malformed argument to `ooc_cmd_load_hub` is NOT "load
            # nothing" -- for a mod-bound session it reloads/resets EVERY hub.
            return web.json_response({"ok": False, "error": "invalid_name"}, status=400)

        if len(segments) == 1:
            try:
                # `ooc_cmd_load_hub` uses its raw argument text verbatim as the
                # filename (no `shlex.split`) -- pass it through unquoted.
                output = session.execute_command("load_hub", name)
            except SessionInvalid:
                return web.json_response({"error": "session_invalid"}, status=401)
            if _command_ok(output):
                self._push_areas_changed(session)
            return _command_response(output)

        # Multi-segment (subfolder) name: `ooc_cmd_load_hub` also strips every
        # "/" from its argument. Resolve+validate ourselves, stage a copy under a
        # throwaway top-level temp name, and run the real command against it.
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

    # -- generic yaml file API -----------------------------------------

    async def handle_data_files(self, request):
        session, err = self._require_session_and_gate(request)
        if err is not None:
            return err
        kind = request.match_info.get("kind", "")
        # Mods can list every hub on the server (see handle_hub_saves); other
        # kinds have no private-name restriction, so _list_data_files is fine
        # for them either way.
        if kind == "hubs":
            files = _list_data_files("hubs") if session.bound_client.is_mod else _public_data_files("hubs")
        else:
            files = _public_data_files(kind)
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

    async def handle_data_file_load(self, request):
        """
        POST /api/gm/data/{kind}/load -- apply a saved yaml file to the live hub,
        per kind: `charlists` -> `/charlist` (lowercased), `musiclists` ->
        `/hub_musiclist`, `character_data` -> `/load_character_data`, `evidence`
        -> `/evidence_load` (or `/evidence_overlay`) into the GM's current area.
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

    # -- charlist editor -------------------------------------------------

    async def handle_charlist_get(self, request):
        session = request["gm_session"]
        if not session.is_valid():
            return web.json_response({"error": "session_invalid"}, status=401)
        hub = session.current_hub()
        return web.json_response({
            "ok": True,
            "characters": list(hub.char_list),
            # Recursive (like `_list_data_files`'s editable side) so a charlist
            # previously saved under a subfolder name shows up here too.
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
            # `AreaManager.load_characters()` no-ops whenever the requested name
            # already matches the hub's current ref -- reset the ref first so the
            # reload below actually runs.
            hub.char_list_ref = ""

        try:
            # Same underlying mechanism/gate as `/charlist <name>` -- an unsaved
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

    # -- music yaml editor -----------------------------------------------

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
            # No (valid, on-disk) ref -- serialize the live in-memory list the
            # same way `/musiclist_save` writes it to disk.
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




