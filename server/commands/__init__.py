import functools
import inspect
import shlex

from ..exceptions import ArgumentError


_UNSET = object()


def tokens_str(text):
    """Shlex-split and rejoin text, unquoting quoted words while keeping
    spaces. Used as a `rest` arg converter for commands that previously did
    `\" \".join(shlex.split(arg))`.
    """
    return " ".join(shlex.split(text))


class Arg:
    """Declare one positional argument of an `ooc_cmd_*` command.

    Arguments bind left-to-right to the tokens of the raw command line,
    shlex-style (double/single quotes and backslash escapes are honored, so
    values containing spaces can be quoted). Required arguments must come
    first; once an argument with a `default` appears, every later argument
    must also provide one. At most one `rest`/`variadic` argument is allowed
    and it must be the last one.

    :param name: Parameter name; the command function receives the parsed
        value under this keyword and error messages reference it.
    :param type: Converter applied to the raw token(s). `str`, `int` and
        `bool` (on/off/true/false/1/0/yes/no) are handled natively; any
        other callable is used as a custom converter.
    :param choices: Sequence of allowed input values; matching is
        case-insensitive and the matched entry (canonical casing/type) is
        returned.
    :param default: Value used when the user omits the argument. Providing a
        default makes the argument optional.
    :param rest: Capture the rest of the line, un-split (whitespace and
        quoting preserved), as a single string. Only valid as the last
        argument.
    :param variadic: Collect every remaining token into a list, converting
        each one with `type`. Only valid as the last argument.
    """

    def __init__(
        self,
        name,
        type=str,
        *,
        required=None,
        default=_UNSET,
        choices=None,
        rest=False,
        variadic=False,
        help=None,    ):
        if rest and variadic:
            raise ValueError(f"Arg '{name}' cannot be both rest and variadic.")
        if default is not _UNSET and required:
            raise ValueError(
                f"Arg '{name}' cannot be both required and have a default."
            )
        self.name = name
        self.type = type
        self.required = required if required is not None else default is _UNSET
        self.default = default if default is not _UNSET else None
        self.choices = choices
        self.rest = rest
        self.variadic = variadic
        self.help = help


_TRUE_VALUES = {"true", "on", "1", "yes"}
_FALSE_VALUES = {"false", "off", "0", "no"}


def _tokenize(arg):
    """Shlex-style tokenizer that also records each token's character span.

    Returns a list of `(token, start, end)` tuples. The quoting rules mirror
    `shlex.split(posix=True)` closely enough for chat input, while exposing
    token positions so `rest` arguments can capture the untouched remainder.
    """
    tokens = []
    i, n = 0, len(arg)
    while i < n:
        while i < n and arg[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        out = []
        while i < n and not arg[i].isspace():
            ch = arg[i]
            if ch in ('"', "'"):
                quote = ch
                i += 1
                while i < n:
                    c = arg[i]
                    if c == quote:
                        i += 1
                        break
                    if c == "\\" and i + 1 < n:
                        out.append(arg[i + 1])
                        i += 2
                    else:
                        out.append(c)
                        i += 1
            elif ch == "\\" and i + 1 < n:
                out.append(arg[i + 1])
                i += 2
            else:
                out.append(ch)
                i += 1
        tokens.append(("".join(out), start, i))
    return tokens


def _msg(why, usage):
    return f"{why} {usage}" if usage else why


def _parse_bool(name, raw):
    lowered = raw.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ArgumentError(
        f"Invalid value for {name} ('{raw}'). Expected on/off (or true/false/1/0)."
    )


def _convert(name, raw, spec, usage):
    if spec.choices is not None:
        for choice in spec.choices:
            if str(raw).lower() == str(choice).lower():
                return choice
        expected = ", ".join(f"'{c}'" for c in spec.choices)
        raise ArgumentError(
            _msg(
                f"Invalid value for {name} ('{raw}'). Expected one of: {expected}.",
                usage,
            )
        )
    try:
        if spec.type is bool:
            return _parse_bool(name, raw)
        if spec.type is int:
            return int(raw)
        if spec.type is str:
            return raw
        return spec.type(raw)
    except (ValueError, TypeError):
        if spec.type is int:
            raise ArgumentError(_msg(f"{name} must be a number.", usage))
        raise ArgumentError(_msg(f"Invalid value for {name} ('{raw}').", usage))


def parse_command_args(raw, args, usage=""):
    """Parse a raw command line against an argument spec.

    Returns a dict mapping each declared argument name to its parsed value.
    Raises `ArgumentError` (including the command's usage line when one is
    known) on missing, extra or invalid arguments.
    """
    if not isinstance(raw, str):
        raw = "" if raw is None else str(raw)
    if not args:
        if raw.strip():
            raise ArgumentError(_msg("This command takes no arguments.", usage))
        return {}

    tokens = _tokenize(raw)
    consumed = 0
    values = {}
    for spec in args:
        if spec.rest:
            if consumed == 0:
                rest = raw
            else:
                rest = raw[tokens[consumed - 1][2]:]
            if spec.type is str:
                values[spec.name] = rest.strip()
            else:
                values[spec.name] = _convert(spec.name, rest, spec, usage)
            consumed = len(tokens)
            break
        if spec.variadic:
            remaining = tokens[consumed:]
            if not remaining:
                if spec.required:
                    raise ArgumentError(_msg("Not enough arguments.", usage))
                values[spec.name] = spec.default
            else:
                values[spec.name] = [
                    _convert(spec.name, token[0], spec, usage) for token in remaining
                ]
            consumed = len(tokens)
            break
        if consumed < len(tokens):
            values[spec.name] = _convert(spec.name, tokens[consumed][0], spec, usage)
            consumed += 1
        elif spec.required:
            raise ArgumentError(_msg("Not enough arguments.", usage))
        else:
            values[spec.name] = spec.default
    if consumed < len(tokens):
        raise ArgumentError(_msg("Too many arguments.", usage))
    return values


def _extract_usage(func):
    """Pull the `Usage:` line out of a command's docstring."""
    doc = inspect.getdoc(func) or ""
    lines = doc.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("usage:"):
            if stripped.lower() == "usage:":
                for nxt in lines[idx + 1:]:
                    if nxt.strip():
                        return f"Usage: {nxt.strip()}"
                return "Usage:"
            return stripped
    return ""


def command(*args, usage=None):
    """Declare the argument spec of an `ooc_cmd_*` function.

    The decorated function keeps its `ooc_cmd_<name>` identity and can still
    be called the legacy way -- `func(client, raw_arg_string)` -- while its
    body receives every declared argument as a keyword. Missing/extra
    arguments and conversion errors raise a standardized `ArgumentError`
    that includes the docstring's `Usage:` line.

    Use inside `@mod_only(...)`: `@mod_only() @command(...) def ooc_cmd_x(client, ...)`.
    """
    specs = [a if isinstance(a, Arg) else Arg(a) for a in args]
    seen_optional = False
    for idx, spec in enumerate(specs):
        if spec.rest or spec.variadic:
            if idx != len(specs) - 1:
                raise ValueError(
                    f"Arg '{spec.name}' must be the last declared argument."
                )
        if not spec.required:
            seen_optional = True
        elif seen_optional:
            raise ValueError(
                f"Required arg '{spec.name}' follows an optional argument."
            )

    def decorator(func):
        usage_line = _extract_usage(func) if usage is None else usage

        @functools.wraps(func)
        def wrapper(client, arg=None, *extra, **kwargs):
            if isinstance(arg, dict):
                parsed = dict(arg)
            else:
                parsed = parse_command_args(arg, specs, usage_line)
            return func(client, **parsed)

        wrapper.command_spec = tuple(specs)
        wrapper.command_usage = usage_line
        return wrapper

    return decorator


def resolve_command(server, cmd):
    """
    Resolve a command name to its `ooc_cmd_<name>` function, following the
    server's command aliases. Returns `None` if the command doesn't exist.
    """
    import sys

    me = sys.modules[__name__]
    called_function = f"ooc_cmd_{cmd}"
    if len(server.command_aliases) > 0 and not hasattr(me, called_function):
        if cmd in server.command_aliases:
            called_function = f"ooc_cmd_{server.command_aliases[cmd]}"
    if not hasattr(me, called_function):
        return None
    return getattr(me, called_function)


def call(client, cmd, arg):
    func = resolve_command(client.server, cmd)
    if func is None:
        client.send_ooc(
            f"Invalid command: {cmd}. Use /help to find up-to-date commands."
        )
        return
    func(client, arg)


def submodules():
    """Get all command-related submodules.

    Only modules that actually belong to the `server.commands` package are
    yielded -- stdlib imports (`functools`, `inspect`, `shlex`) that live at
    package scope must not show up as help categories.
    """
    import sys
    import inspect

    me = sys.modules[__name__]
    for _, v in inspect.getmembers(me):
        if inspect.ismodule(v) and v.__name__.startswith(__name__ + "."):
            yield v


def reload():
    """Reload all submodules."""
    import sys
    import importlib

    me = sys.modules[__name__]
    for module in submodules():
        m = importlib.reload(module)
        for f in m.__all__:
            me.__dict__[f] = m.__dict__[f]

    # The GM panel caches its auto-generated command catalog; drop the cache
    # so the panel picks up the freshly reloaded command definitions.
    try:
        from server.web_view.gm_panel.commands_meta import CommandLister

        CommandLister.invalidate()
    except ImportError:
        pass


def help(command):
    import sys
    import inspect

    try:
        doc = inspect.getdoc(getattr(sys.modules[__name__], command))
    except AttributeError:
        raise
    return doc


def list_submodules():
    """
    Lists all known submodules.
    """
    subm = ""
    for module in submodules():
        # Only return the name of the module and not the whole hierarchy
        name = module.__name__.split(".")[-1]
        subm += f"{name}\n"
    return subm


def list_commands(submodule=""):
    """
    Lists all known commands.
    :param submodule: Which submodule to search. Lists all commands if blank. Raises attribute error if submodule not found.
    """
    import inspect

    cmds = ""
    modules = [
        a
        for a in submodules()
        if submodule == "" or a.__name__.split(".")[-1] == submodule
    ]
    if len(modules) == 0:
        raise AttributeError
    for module in modules:
        for func in module.__all__:
            doc = inspect.getdoc(module.__dict__[func])
            if doc is None:
                doc = "(no docs)"
            else:
                # Find the first sentence (assuming it ends in a period).
                doc = doc[: doc.find(".") + 1]
            prefix = "ooc_cmd_"
            if func.startswith(prefix):
                func = func[len(prefix):]
            cmds += f"{func} - {doc}\n"
    return cmds


def mod_only(area_owners=False, hub_owners=False):
    import functools
    from ..exceptions import ClientError

    def decorator(func):
        @functools.wraps(func)
        def wrapper_mod_only(client, arg, *args, **kwargs):
            # System executors (e.g. RemoteClient with is_gm=True) act as a
            # GM: they pass area-owner and hub-owner gates but never mod-only.
            is_gm = getattr(client, "is_gm", False)
            if (
                not client.is_mod
                and (not area_owners or not (client in client.area.owners or is_gm))
                and (not hub_owners or not (client in client.area.area_manager.owners or is_gm))
            ):
                raise ClientError("You must be authorized to do that.")
            func(client, arg, *args, **kwargs)

        return wrapper_mod_only

    return decorator


# Note that only the members of __all__ in each module will be imported.
# There must be an __all__ in each module in order for reloading
# to work properly.
from .admin import *
from .area_access import *
from .areas import *
from .casing import *
from .character import *
from .fun import *
from .hubs import *
from .messaging import *
from .music import *
from .roleplay import *
from .battle import *
from .inventory import *
