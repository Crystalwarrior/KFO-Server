"""
Single source of truth for the area fields/prefs the GM panel exposes.

Declares, exactly once: the scalar fields the Areas-tab inspector shows, which
of them are editable, how the frontend should render each (input control type),
which boolean prefs a CM may toggle (vs. GM-only), and how each editable field
is written back through the real command layer.

Consumers that derive from this table instead of re-declaring it:

- ``server/commands/hubs.py`` ``ooc_cmd_area_pref``  -- the ``cm_allowed`` gate
- ``server/web_view/gm_panel`` serializers           -- field lists + meta + pref badges
- ``server/web_view/gm_panel`` ``AreaRoutes.handle_edit_area`` -- write dispatch
  (previously a ~130-line if/elif chain; now a single registry lookup)

Adding an editable area field therefore means: (1) the real ``Area`` attribute
and its command (if any) in ``server/``, and (2) ONE ``AREA_WRITE_STRATEGIES``
entry (+ optionally a ``AREA_FIELD_META`` entry for its control type). The
serializer and route handler pick it up automatically.

This module is a LEAF: it imports only ``server.exceptions`` (itself a leaf) so
``area.py``, the command layer, ``scripting.py`` and the web view can all import
it without circular imports. Write strategies duck-type ``session`` (they never
import ``GMSession``).
"""

from server.exceptions import ClientError


# =============================================================================
# Boolean prefs a CM may toggle (not badged "[gm]")
# =============================================================================

# Mirrored by `ooc_cmd_area_pref`'s `cm_allowed` gate (server/commands/hubs.py),
# which now imports this exact set instead of keeping its own copy.
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


# =============================================================================
# Scalar fields exposed in the inspector (read-only + editable)
# =============================================================================

# Every field name here must exist on ``Area`` (server/area.py) either as an
# instance attribute set in ``__init__`` or as a computed ``@property``.
AREA_SCALAR_FIELDS = (
    "name", "background", "background_suffix", "overlay", "dark",
    "locked", "status", "doc", "desc", "move_delay", "max_players",
    "evidence_mod", "pos_lock", "abbreviation", "ambience", "broadcast_list",
    "background_dark", "pos_dark", "desc_dark", "msg_delay", "music_ref",
    "hp_def", "hp_pro", "music", "password", "triggers",
    "cross_swords_song_start", "cross_swords_song_end", "cross_swords_song_concede",
    "scrum_debate_song_start", "scrum_debate_song_end", "scrum_debate_song_concede",
    "panic_talk_action_song_start", "panic_talk_action_song_end",
    "panic_talk_action_song_concede",
)


# =============================================================================
# Input-control metadata for the frontend (editable fields only; `pos_lock` is
# special-cased in the frontend and deliberately absent)
# =============================================================================

AREA_FIELD_META = {
    "name": {"input": "text"},
    "desc": {"input": "text"},
    "doc": {"input": "text"},
    "max_players": {"input": "number"},
    "status": {"input": "text"},
    "dark": {"input": "checkbox"},
    "locked": {"input": "checkbox"},
    "background_suffix": {"input": "text"},
    "background_dark": {"input": "text"},
    "pos_dark": {"input": "text"},
    "desc_dark": {"input": "text"},
    "password": {"input": "text"},
    "move_delay": {"input": "number"},
    "msg_delay": {"input": "number"},
    "hp_def": {"input": "number", "min": 0, "max": 10},
    "hp_pro": {"input": "number", "min": 0, "max": 10},
    "evidence_mod": {"input": "select", "options": ["FFA", "CM", "Mods", "HiddenCM"]},
    "music_ref": {"input": "select", "options": [], "clearable": True},
    "triggers": {"input": "triggers"},
    "cross_swords_song_start": {"input": "text"},
    "cross_swords_song_end": {"input": "text"},
    "cross_swords_song_concede": {"input": "text"},
    "scrum_debate_song_start": {"input": "text"},
    "scrum_debate_song_end": {"input": "text"},
    "scrum_debate_song_concede": {"input": "text"},
    "panic_talk_action_song_start": {"input": "text"},
    "panic_talk_action_song_end": {"input": "text"},
    "panic_talk_action_song_concede": {"input": "text"},
}


# =============================================================================
# Write strategies: field -> callable(session, area, value, extra) -> output list
# =============================================================================

def _as_int(value, err_label):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(err_label)


def _in_area(cmd, clear_cmd=None, arg_fn=None):
    """A strategy that runs a command on the (shadowed) target area."""
    def strategy(session, area, value, extra):
        if clear_cmd is not None and value == "":
            return session.execute_command_in_area(area, clear_cmd, "")
        arg = arg_fn(value) if arg_fn is not None else value
        return session.execute_command_in_area(area, cmd, arg)
    return strategy


def _validated_in_area(cmd, err_label, arg_fn=None, range_check=None):
    """Like `_in_area`, but validates `value` as an int first (passing it on)."""
    def strategy(session, area, value, extra):
        try:
            n = _as_int(value, err_label)
            if range_check is not None and not range_check(n):
                raise ValueError(err_label)
        except ValueError as ex:
            return [f"[ERROR] {ex}"]
        arg = arg_fn(n) if arg_fn is not None else value
        return session.execute_command_in_area(area, cmd, arg)
    return strategy


def _direct_set(attr, key=None, coerce=None, note=None):
    """A strategy that writes the attribute directly via `session.set_area_direct`."""
    def strategy(session, area, value, extra):
        val = value
        if coerce is not None:
            try:
                val = coerce(value)
            except ValueError as ex:
                return [f"[ERROR] {ex}"]
        try:
            if not session.set_area_direct(area, attr, val, key=key):
                return ["[ERROR] Could not update area field."]
            return [f"{attr} updated." if note is None else note]
        except ClientError as ex:
            return [f"[ERROR] {ex}"]
    return strategy


def _triggers_strategy(session, area, value, extra):
    trigger = str(extra.get("trigger", "")).strip()
    if trigger not in area.triggers:
        return [f"[ERROR] Invalid trigger: {trigger}"]
    if value == "":
        return _direct_set("triggers", key=trigger, note=f"Cleared trigger '{trigger}'.")(
            session, area, value, extra
        )
    return session.execute_command_in_area(area, "trigger", f"{trigger} {value}")


_MINIGAME_CODE = {"cross_swords": "cs", "scrum_debate": "sd", "panic_talk_action": "pta"}
_MINIGAME_CONDITIONS = ("start", "end", "concede")


def _minigame_song_strategy(field, code, condition):
    def strategy(session, area, value, extra):
        if value == "":
            return _direct_set(field)(session, area, value, extra)
        return session.execute_command_in_area(area, f"minigame_{condition}_song", f"{code} {value}")
    return strategy


def _hp_strategy(side):
    def strategy(session, area, value, extra):
        try:
            hp = _as_int(value, "HP must be an integer between 0 and 10.")
            if not 0 <= hp <= 10:
                raise ValueError("HP must be between 0 and 10.")
        except ValueError as ex:
            return [f"[ERROR] {ex}"]
        return session.execute_command_in_area(area, "hpset", f"{side} {hp}")
    return strategy


AREA_WRITE_STRATEGIES = {
    "name": lambda s, area, value, extra: s.execute_command("area_rename", f"{area.id} {value}"),
    "desc": _in_area("desc", clear_cmd="desc_clear"),
    "doc": _in_area("doc", clear_cmd="cleardoc"),
    "max_players": _validated_in_area("max_players", "max_players must be an integer."),
    "pos_lock": _in_area("pos_lock", clear_cmd="pos_lock_clear"),
    "status": _in_area("status"),
    "dark": _in_area("lights", arg_fn=lambda v: "off" if v == "true" else "on"),
    "locked": lambda s, area, value, extra: s.execute_command("unlock" if value == "false" else "lock", str(area.id)),
    "desc_dark": _in_area("desc_dark", clear_cmd="desc_dark_clear"),
    "background_suffix": _in_area("bg_suffix"),
    "move_delay": _validated_in_area(
        "area_move_delay", "Move delay must be an integer between -1800 and 1800.",
        range_check=lambda n: -1800 <= n <= 1800,
    ),
    "evidence_mod": lambda s, area, value, extra: (
        [f"[ERROR] Invalid evidence mod. Use FFA, CM, Mods or HiddenCM."]
        if value not in ("FFA", "CM", "Mods", "HiddenCM")
        else s.execute_command_in_area(area, "evidence_mod", value)
    ),
    "music_ref": _in_area("area_musiclist"),
    "password": lambda s, area, value, extra: s.execute_command("setpw", f"{area.id} {value}".rstrip()),
    "hp_def": _hp_strategy("def"),
    "hp_pro": _hp_strategy("pro"),
    "triggers": _triggers_strategy,
    "background_dark": _direct_set("background_dark"),
    "pos_dark": _direct_set("pos_dark"),
    "msg_delay": _direct_set("msg_delay", coerce=lambda v: _as_int(v, "msg_delay must be an integer.")),
}


# Minigame song scalars are generated from the same declaration table so a new
# minigame or song slot only needs one `_MINIGAME_CODE` entry.
for _minigame, _code in _MINIGAME_CODE.items():
    for _condition in _MINIGAME_CONDITIONS:
        _field = f"{_minigame}_song_{_condition}"
        AREA_WRITE_STRATEGIES[_field] = _minigame_song_strategy(_field, _code, _condition)


# Editable fields == the set of fields with a write strategy.
AREA_EDITABLE_FIELDS = frozenset(AREA_WRITE_STRATEGIES)

