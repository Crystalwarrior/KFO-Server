"""Tests for the MS (IC message) parser."""

from server.network.ms_parser import parse_ms


# Base 15 fields used by all protocols
def _base_args():
    return [
        "1",        # msg_type
        "pre",      # pre
        "folder",   # folder
        "anim",     # anim
        "Hello",    # text
        "def",      # pos
        "sfx",      # sfx
        "1",        # emote_mod (will be converted to int)
        "5",        # cid (will be converted to int)
        "0",        # sfx_delay (will be converted to int)
        "0",        # button
        "0",        # evidence (will be converted to int)
        "0",        # flip (will be converted to int)
        "0",        # ding (will be converted to int)
        "0",        # color (will be converted to int)
    ]


def test_parse_pre26():
    """Test pre-2.6 protocol (15 args)."""
    args = _base_args()
    ms = parse_ms(args)

    assert ms is not None
    assert ms["msg_type"] == "1"
    assert ms["text"] == "Hello"
    assert ms["emote_mod"] == 1
    assert ms["cid"] == 5
    # Check defaults are applied
    assert ms["showname"] == ""
    assert ms["charid_pair"] == -1
    assert ms["pair_order"] == 0
    assert ms["video"] == ""


def test_parse_v26():
    """Test 2.6 protocol (19 args)."""
    args = _base_args() + [
        "TestName",  # showname
        "3",         # charid_pair (INT)
        "10",        # offset_pair (INT)
        "1",         # nonint_pre
    ]
    ms = parse_ms(args)

    assert ms is not None
    assert ms["showname"] == "TestName"
    assert ms["charid_pair"] == 3
    assert ms["offset_pair"] == 10
    assert ms["nonint_pre"] == 1
    # Check defaults for 2.8+ fields
    assert ms["sfx_looping"] == "0"
    assert ms["effect"] == ""


def test_parse_v28():
    """Test 2.8 protocol (26 args)."""
    args = _base_args() + [
        "ShowName",  # showname
        "7^1",       # charid_pair (STR with pair_order)
        "15",        # offset_pair (STR)
        "0",         # nonint_pre
        "1",         # sfx_looping
        "1",         # screenshake
        "1-5",       # frames_shake
        "2-3",       # frames_realization
        "4-6",       # frames_sfx
        "1",         # additive
        "effect1",   # effect
    ]
    ms = parse_ms(args)

    assert ms is not None
    assert ms["showname"] == "ShowName"
    assert ms["charid_pair"] == 7
    assert ms["pair_order"] == "1"
    assert ms["offset_pair"] == "15"
    assert ms["sfx_looping"] == "1"
    assert ms["screenshake"] == 1
    assert ms["frames_shake"] == "1-5"
    assert ms["effect"] == "effect1"
    # Check defaults
    assert ms["third_charid"] == -1
    assert ms["video"] == ""


def test_parse_v28_no_pair_order():
    """Test 2.8 protocol without pair_order in charid_pair."""
    args = _base_args() + [
        "",          # showname
        "5",         # charid_pair (no ^)
        "0",         # offset_pair
        "0",         # nonint_pre
        "0",         # sfx_looping
        "0",         # screenshake
        "",          # frames_shake
        "",          # frames_realization
        "",          # frames_sfx
        "0",         # additive
        "",          # effect
    ]
    ms = parse_ms(args)

    assert ms is not None
    assert ms["charid_pair"] == 5
    assert ms["pair_order"] == 0  # default


def test_parse_ao_golden():
    """Test AO Golden protocol (27 args)."""
    args = _base_args() + [
        "Name",      # showname
        "2^0",       # charid_pair
        "5",         # offset_pair
        "0",         # nonint_pre
        "0",         # sfx_looping
        "0",         # screenshake
        "",          # frames_shake
        "",          # frames_realization
        "",          # frames_sfx
        "0",         # additive
        "",          # effect
        "8",         # third_charid
    ]
    ms = parse_ms(args)

    assert ms is not None
    assert ms["charid_pair"] == 2
    assert ms["pair_order"] == "0"
    assert ms["third_charid"] == 8
    assert ms["video"] == ""  # default


def test_parse_kfo():
    """Test KFO protocol (28 args)."""
    args = _base_args() + [
        "KFOName",   # showname
        "4^2",       # charid_pair
        "-10",       # offset_pair
        "1",         # nonint_pre
        "1",         # sfx_looping
        "0",         # screenshake
        "",          # frames_shake
        "",          # frames_realization
        "",          # frames_sfx
        "0",         # additive
        "zoom",      # effect
        "9",         # third_charid
        "video.webm",  # video
    ]
    ms = parse_ms(args)

    assert ms is not None
    assert ms["showname"] == "KFOName"
    assert ms["charid_pair"] == 4
    assert ms["pair_order"] == "2"
    assert ms["third_charid"] == 9
    assert ms["video"] == "video.webm"
    assert ms["effect"] == "zoom"


def test_parse_dro():
    """Test DRO 1.1.0 protocol (18 args)."""
    args = _base_args() + [
        "DROName",   # showname
        "vid.webm",  # video
        "0",         # blankpost
    ]
    ms = parse_ms(args)

    assert ms is not None
    assert ms["showname"] == "DROName"
    assert ms["video"] == "vid.webm"
    # DRO uses defaults for pair fields
    assert ms["charid_pair"] == -1
    assert ms["pair_order"] == 0


def test_parse_dro_ding_normalization():
    """Test DRO normalizes ding to 0 or 1."""
    args = _base_args() + ["", "", "0"]
    # Set ding to something other than 0 or 1
    args[13] = "5"
    ms = parse_ms(args)

    assert ms is not None
    assert ms["ding"] == 0  # normalized

    # Test ding=1 is preserved
    args[13] = "1"
    ms = parse_ms(args)
    assert ms["ding"] == 1


def test_parse_invalid_returns_none():
    """Test that invalid args return None."""
    # Too few args
    assert parse_ms(["1", "2", "3"]) is None

    # Wrong number of args (between valid schemas)
    assert parse_ms(_base_args() + ["extra"]) is None


def test_parse_invalid_int_returns_none():
    """Test that invalid INT fields return None."""
    args = _base_args()
    args[7] = "not_an_int"  # emote_mod should be INT
    assert parse_ms(args) is None


def test_parse_invalid_pair_order_returns_none():
    """Test that invalid charid_pair parsing returns None."""
    args = _base_args() + [
        "",
        "not_a_number^1",  # invalid charid_pair
        "0",
        "0",
        "0",
        "0",
        "",
        "",
        "",
        "0",
        "",
    ]
    assert parse_ms(args) is None


def test_parse_empty_optional_strings():
    """Test that empty strings are allowed for STR_OR_EMPTY fields."""
    args = _base_args()
    args[1] = ""   # pre (STR_OR_EMPTY)
    args[3] = ""   # anim (STR_OR_EMPTY)
    args[4] = ""   # text (STR_OR_EMPTY)
    ms = parse_ms(args)

    assert ms is not None
    assert ms["pre"] == ""
    assert ms["anim"] == ""
    assert ms["text"] == ""
