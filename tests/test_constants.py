from server.constants import (
    censor,
    contains_URL,
    derelative,
    dezalgo,
    encode_ao_packet,
    remove_URL,
)


def test_remove_and_contains_url():
    s = "http://example.com/page"
    assert contains_URL(s) is True
    cleaned = remove_URL(s)
    # No http-URLs should remain
    assert "http://" not in cleaned and "https://" not in cleaned


def test_dezalgo_removes_excessive_combining_marks():
    base = "a"
    combining = "\u0301"  # COMBINING ACUTE ACCENT
    s = base + combining * 4  # 4 combining marks in a row
    # tolerance is 3 by default, so 3 or more in a row will be stripped
    assert dezalgo(s) == base


def test_censor_whole_word_replacement():
    text = "Bad words are bad, BAD!"
    censored = censor(text, censor_list=["bad"], replace="#", whole_words=True)
    # Whole word matches for "bad" should be replaced case-insensitively
    assert "bad" not in censored.lower()
    # Replacement length should match the word length (3)
    assert "###" in censored


def test_encode_ao_packet_replaces_specials():
    params = [
        ("#", "%", "$", "&"),
        "plain",
    ]
    encoded = encode_ao_packet(params)
    # tuple should be preserved with replacements
    t = encoded[0]
    assert t == ("<num>", "<percent>", "<dollar>", "<and>")
    assert encoded[1] == "plain"


def test_derelative_removes_parent_traversal():
    s = "../../etc/passwd"
    assert ".." not in derelative(s)
