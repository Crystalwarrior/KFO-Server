"""Parser for MS (IC message) network commands."""

from enum import Enum


class ArgType(Enum):
    """Represents the data type of an argument for a network command."""
    STR = 1
    STR_OR_EMPTY = 2
    INT = 3
    INT_OR_STR = 3


# Base fields shared by all protocol versions (indices 0-14)
_BASE = [
    ("msg_type", ArgType.STR),
    ("pre", ArgType.STR_OR_EMPTY),
    ("folder", ArgType.STR),
    ("anim", ArgType.STR_OR_EMPTY),
    ("text", ArgType.STR_OR_EMPTY),
    ("pos", ArgType.STR),
    ("sfx", ArgType.STR),
    ("emote_mod", ArgType.INT),
    ("cid", ArgType.INT),
    ("sfx_delay", ArgType.INT),
    ("button", ArgType.INT_OR_STR),
    ("evidence", ArgType.INT),
    ("flip", ArgType.INT),
    ("ding", ArgType.INT),
    ("color", ArgType.INT),
]

# 2.6: charid_pair/offset_pair as INT
_V26 = _BASE + [
    ("showname", ArgType.STR_OR_EMPTY),
    ("charid_pair", ArgType.INT),
    ("offset_pair", ArgType.INT),
    ("nonint_pre", ArgType.INT),
]

# 2.8+: charid_pair/offset_pair as STR (supports pair_order via "id^order")
_V28 = _BASE + [
    ("showname", ArgType.STR_OR_EMPTY),
    ("charid_pair", ArgType.STR),
    ("offset_pair", ArgType.STR),
    ("nonint_pre", ArgType.INT),
    ("sfx_looping", ArgType.STR),
    ("screenshake", ArgType.INT),
    ("frames_shake", ArgType.STR_OR_EMPTY),
    ("frames_realization", ArgType.STR_OR_EMPTY),
    ("frames_sfx", ArgType.STR_OR_EMPTY),
    ("additive", ArgType.INT),
    ("effect", ArgType.STR_OR_EMPTY),
]

# DRO 1.1.0: different layout after base
_DRO = _BASE + [
    ("showname", ArgType.STR_OR_EMPTY),
    ("video", ArgType.STR_OR_EMPTY),
    ("blankpost", ArgType.INT),
]

# Schemas: (name, fields, needs_pair_parsing)
_SCHEMAS = [
    ("kfo", _V28 + [("third_charid", ArgType.INT), ("video", ArgType.STR_OR_EMPTY)], True),
    ("ao_golden", _V28 + [("third_charid", ArgType.INT)], True),
    ("v28", _V28, True),
    ("v26", _V26, False),
    ("dro", _DRO, False),
    ("pre26", _BASE, False),
]

_DEFAULTS = {
    "showname": "",
    "charid_pair": -1,
    "offset_pair": 0,
    "nonint_pre": 0,
    "sfx_looping": "0",
    "screenshake": 0,
    "frames_shake": "",
    "frames_realization": "",
    "frames_sfx": "",
    "additive": 0,
    "effect": "",
    "pair_order": 0,
    "third_charid": -1,
    "video": "",
}


def _validate(args, fields):
    """Check if args match the field types and convert INTs in place."""
    if len(args) != len(fields):
        return False
    for i, (name, typ) in enumerate(fields):
        if len(str(args[i])) == 0 and typ != ArgType.STR_OR_EMPTY:
            return False
        if typ == ArgType.INT:
            try:
                args[i] = int(args[i])
            except ValueError:
                return False
    return True


def parse_ms(args):
    """Parse MS message arguments into a dict.

    Tries protocol schemas from most complete to least complete.

    :param args: raw arguments from the MS network command
    :returns: dict with all MS fields, or None if parsing failed
    """
    for schema_name, fields, needs_pair_parsing in _SCHEMAS:
        if _validate(args, fields):
            ms = {f[0]: args[i] for i, f in enumerate(fields)}

            # Fill defaults for missing optional fields
            for key, default in _DEFAULTS.items():
                ms.setdefault(key, default)

            # DRO normalizes ding to 0 or 1
            if schema_name == "dro" and ms["ding"] != 1:
                ms["ding"] = 0

            # 2.8+ encodes pair_order in charid_pair as "id^order"
            if needs_pair_parsing:
                try:
                    pair_args = ms["charid_pair"].split("^")
                    ms["charid_pair"] = int(pair_args[0])
                    if len(pair_args) > 1:
                        ms["pair_order"] = pair_args[1]
                except ValueError:
                    return None

            return ms

    return None
