import pytest

from server.commands import Arg, command, parse_command_args, tokens_str
from server.exceptions import ArgumentError


def parse(raw, *args, usage=""):
    return parse_command_args(raw, args, usage)


# --- terminal parsing ---


def test_no_args_command_rejects_input():
    assert parse("") == {}
    with pytest.raises(ArgumentError, match="takes no arguments"):
        parse("x")


def test_required_then_optional_positional():
    spec = (Arg("a", int), Arg("b", default=""))
    assert parse("5", *spec) == {"a": 5, "b": ""}
    assert parse("5 x", *spec) == {"a": 5, "b": "x"}


def test_missing_extraneous_and_bad_int_errors_include_usage():
    with pytest.raises(ArgumentError, match=r"Not enough arguments\. Usage: /x <a>"):
        parse("", Arg("a", int), usage="Usage: /x <a>")
    with pytest.raises(ArgumentError, match=r"Too many arguments\. Usage: /x <a>"):
        parse("1 2", Arg("a", int), usage="Usage: /x <a>")
    with pytest.raises(ArgumentError, match=r"a must be a number\. Usage: /x <a>"):
        parse("x", Arg("a", int), usage="Usage: /x <a>")


def test_quotes_and_escapes_are_honored():
    assert parse('"a b" c', Arg("x"), Arg("y")) == {"x": "a b", "y": "c"}
    assert parse("'a b'", Arg("x")) == {"x": "a b"}
    assert parse("a\\ b", Arg("x")) == {"x": "a b"}


def test_bool_accepts_common_toggles():
    spec = (Arg("tog", bool, default=None),)
    assert parse("on", *spec) == {"tog": True}
    assert parse("OFF", *spec) == {"tog": False}
    assert parse("1", *spec) == {"tog": True}
    assert parse("", *spec) == {"tog": None}
    with pytest.raises(ArgumentError, match="Invalid value for tog"):
        parse("maybe", *spec)


def test_choices_match_case_insensitively_and_return_canonical():
    spec = (Arg("side", choices=["pro", "def"]),)
    assert parse("PRO", *spec) == {"side": "pro"}
    assert parse("Def", *spec) == {"side": "def"}
    with pytest.raises(ArgumentError, match="Expected one of"):
        parse("left", *spec)


# --- rest / variadic ---


def test_rest_preserves_raw_text():
    assert parse("hello   world", Arg("arg", rest=True)) == {
        "arg": "hello   world"
    }
    assert parse("", Arg("arg", rest=True, default="")) == {"arg": ""}
    assert tokens_str("a  'b c'  d") == "a b c d"


def test_rest_after_fixed_args_keeps_remainder():
    assert parse("x 'hi' yo", Arg("a"), Arg("arg", rest=True, default="")) == {
        "a": "x",
        "arg": "'hi' yo",
    }


def test_variadic_collects_and_converts_all_tokens():
    assert parse("1 2 3", Arg("ids", int, variadic=True)) == {"ids": [1, 2, 3]}
    assert parse("", Arg("ids", int, variadic=True, default=[])) == {"ids": []}
    with pytest.raises(ArgumentError, match="ids must be a number"):
        parse("1 x", Arg("ids", int, variadic=True))
    with pytest.raises(ArgumentError, match="Not enough arguments"):
        parse("", Arg("ids", int, variadic=True))


def test_rest_and_variadic_must_be_last():
    with pytest.raises(ValueError, match="last"):
        Arg("after", variadic=True) and command(Arg("pre"), Arg("x", variadic=True), Arg("y"))


@pytest.mark.parametrize(
    "spec_kwargs",
    [
        {"required": True, "default": ""},
        {"rest": True, "variadic": True},
    ],
)
def test_invalid_arg_configurations_raise(spec_kwargs):
    with pytest.raises(ValueError):
        Arg("x", **spec_kwargs)


def test_required_after_optional_spec_rejected():
    with pytest.raises(ValueError, match="follows an optional argument"):
        command(Arg("a", default=""), Arg("b"))


# --- decorator ---


def test_decorator_still_accepts_raw_string():
    @command(Arg("target", int, required=True), Arg("reason", default="", rest=True))
    def ooc_cmd_kick(client, target, reason):
        return client, target, reason

    assert ooc_cmd_kick(None, "5 this is why") == (None, 5, "this is why")


def test_decorator_preserves_name_doc_and_spec():
    @command(Arg("a", int))
    def ooc_cmd_test_deco(client, a):
        """Docstring here.
        Usage: /test_deco <a>
        """

    assert ooc_cmd_test_deco.__name__ == "ooc_cmd_test_deco"
    assert "Docstring here" in ooc_cmd_test_deco.__doc__
    assert ooc_cmd_test_deco.command_spec[0].name == "a"


def test_decorator_accepts_no_args_and_rejects_input():
    @command()
    def ooc_cmd_quiet(client):
        return "done"

    assert ooc_cmd_quiet(None, "") == "done"
    with pytest.raises(ArgumentError, match="takes no arguments"):
        ooc_cmd_quiet(None, "x")


def test_usage_line_pulled_from_docstring():
    @command(Arg("a", int))
    def ooc_cmd_doc_usage(client, a):
        """Do a thing.
        Usage: /doc_usage <a>
        """

    assert ooc_cmd_doc_usage.command_usage == "Usage: /doc_usage <a>"
    with pytest.raises(ArgumentError, match="Usage: /doc_usage <a>"):
        ooc_cmd_doc_usage(None, "x")


def test_usage_line_continuation_when_usage_on_own_line():
    @command()
    def ooc_cmd_multiline_usage(client):
        """Do a thing.

        Usage:
        /multiline_usage <x>
        """

    assert ooc_cmd_multiline_usage.command_usage == "Usage: /multiline_usage <x>"


def test_raises_inside_command_body_pass_through():
    @command(Arg("n", int))
    def ooc_cmd_bodierr(client, n):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        ooc_cmd_bodierr(None, "5")