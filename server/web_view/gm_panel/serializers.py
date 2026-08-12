"""Serializers: the only code allowed to turn live objects into GM-facing JSON.

Every class here is the sole code path that turns a live `Client`/`Area`/etc.
into a dict for the browser -- no handler may call `vars(...)`/`__dict__` or
hand-roll an object dict inline. Field lists derive from `server/schema` (the
single source of truth) so a new property is serialized automatically.
"""

import os

from server.constants import _SYSTEM_IPID
from server.remote_client import RemoteClient
from server.script_runner import parse_demo_description
from server.schema.area_fields import (
    AREA_EDITABLE_FIELDS,
    AREA_FIELD_META,
    AREA_PREF_CM_ALLOWED,
    AREA_SCALAR_FIELDS,
)
from server.schema.link_props import LINK_PROPERTY_SCHEMA

from server.web_view.gm_panel.storage import DATA_KIND_DIRS


class ClientSerializer:
    """
    Converts a live `Client` into the GM-facing field whitelist.

    This is the ONLY place in the GM panel allowed to turn a `Client` into
    JSON -- no handler may call `vars(client)`/`client.__dict__` or hand-roll a
    client dict inline. That makes "ipid/hdid/ip can never leak to a GM" a
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
    """Converts a live `Area` into a graph node."""

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
        `links` dict. The field names, export names and coercion derive from
        `server/schema/link_props.py` (single source of truth), so a new link
        property is serialized here automatically.
        """
        links = []
        for target_id_str, link in area.links.items():
            try:
                target_id = int(target_id_str)
            except (TypeError, ValueError):
                continue
            item = {"target_id": target_id}
            for prop in LINK_PROPERTY_SCHEMA:
                item[prop.export] = prop.to_json(link.get(prop.name, prop.default))
            links.append(item)
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
            "pos_lock": [str(p) for p in area.pos_lock],
            "client_ids": client_ids,
            "gm_client_ids": gm_ids,
            "cm_client_ids": cm_ids,
            "links": AreaSerializer.links_to_list(area),
            "fully_connected": len(area.links) == 0,
        }


class AreaDetailSerializer:
    """
    Converts a live `Area` into the Areas tab's per-area inspector payload:
    a small allowlist of command-backed scalar fields, every boolean pref
    (dynamically enumerated -- see `AREA_PREF_CM_ALLOWED`), and the full
    directed link list. Like `AreaSerializer`/`ClientSerializer`, this is the
    only place allowed to turn this slice of `Area` into JSON.
    """

    # The scalar-field list, the editable set and the input-control metadata
    # all live once in `server/schema/area_fields.py`; the write dispatch for
    # each editable field lives there too (`AREA_WRITE_STRATEGIES`).
    _SCALAR_FIELDS = AREA_SCALAR_FIELDS
    EDITABLE_FIELDS = AREA_EDITABLE_FIELDS
    FIELD_META = AREA_FIELD_META

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
            # `broadcast_list` holds live `Area` OBJECTS, not ids or strings.
            # Reduce to area ids first so it serializes exactly like
            # `pos_lock` (a list of strings) and never leaks a live object.
            if name == "broadcast_list" and isinstance(value, list):
                value = [getattr(v, "id", v) for v in value]
            # `triggers` is a dict of `{trigger_key: command_string}`; it is
            # its own JSON-safe type, so pass it through as-is.
            if name == "triggers" and isinstance(value, dict):
                fields[name] = {str(k): str(v) for k, v in value.items()}
                continue
            # `pos_lock`/`broadcast_list` are lists; everything else is a
            # str/int. Coerce defensively so a future non-JSON-safe Area
            # attribute added to `AREA_SCALAR_FIELDS` can't leak an
            # unexpected type to the browser.
            if isinstance(value, list):
                value = [str(v) for v in value]
            elif not isinstance(value, (str, int, float, bool)) and value is not None:
                value = str(value)
            fields[name] = value

        # `field_meta` drives the inspector's per-field control type. `music_ref`
        # options are live -- re-scan `storage/musiclists` on every detail load.
        field_meta = {
            name: dict(meta)
            for name, meta in AreaDetailSerializer.FIELD_META.items()
            if name in AreaDetailSerializer.EDITABLE_FIELDS
        }
        if "music_ref" in field_meta:
            music_refs = set()
            for root in (
                DATA_KIND_DIRS["musiclists"],
                os.path.join(DATA_KIND_DIRS["musiclists"], "read_only"),
            ):
                try:
                    for f in os.listdir(root):
                        if f.lower().endswith(".yaml"):
                            music_refs.add(f[:-5])
                except OSError:
                    continue
            field_meta["music_ref"]["options"] = sorted(music_refs)

        return {
            "id": area.id,
            "fields": fields,
            "editable_fields": sorted(AreaDetailSerializer.EDITABLE_FIELDS),
            "field_meta": field_meta,
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
    `desc` field holds a demo script; the underlying `/demo` command and
    `ScriptRunner` machinery are unchanged, only the panel's user-facing
    vocabulary is "evidence" now.
    """

    @staticmethod
    def _out_of_range_warnings(area, instructions):
        """
        Read-only mirror of `Area._warn_demo_out_of_range`'s check, without the
        side effect of broadcasting anything -- just reports the same warnings
        back to the caller so the panel can display them.
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


