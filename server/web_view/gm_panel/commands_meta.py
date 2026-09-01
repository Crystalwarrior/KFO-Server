"""Command-output scrubbing and the auto-generated command catalog."""

import inspect
import re

from server import commands



class CommandOutputScrubber:
    """
    Last-resort redaction pass over captured OOC command output lines.

    Serializers and the command catalog are the primary defenses against
    ipid/hdid/IP reaching a GM; this exists purely as defense in depth, in case
    a future cataloged command ever prints one of these incidentally.
    """

    _IPV4_RE = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    )
    # Require at least 4 colon-separated groups so ordinary "HH:MM:SS"
    # timestamps (3 groups) don't get flagged as IPv6 addresses.
    _IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b")
    _IPID_LABEL_RE = re.compile(r"(?i)\bipid\b\s*[:#=]?\s*[\"']?[\w.\-]+")
    _HDID_LABEL_RE = re.compile(r"(?i)\bhdid\b\s*[:#=]?\s*[\"']?[\w.\-]+")
    _MOD_PROFILE_RE = re.compile(r"(?i)\bmod\s*profile(\s*name)?\s*[:#=]?\s*[\"']?[\w.\- ]+")

    @classmethod
    def scrub(cls, lines):
        return [cls._scrub_line(line) for line in lines]

    @classmethod
    def _scrub_line(cls, line):
        text = str(line)
        text = cls._IPID_LABEL_RE.sub("[redacted]", text)
        text = cls._HDID_LABEL_RE.sub("[redacted]", text)
        text = cls._MOD_PROFILE_RE.sub("[redacted]", text)
        text = cls._IPV6_RE.sub("[redacted]", text)
        text = cls._IPV4_RE.sub("[redacted]", text)
        return text


class CommandLister:
    """
    Auto-generates the Commands tab's searchable cookbook from the command
    layer's own submodules (`server/commands/`): each submodule's `__all__`
    (or, failing that, every `ooc_cmd_*` in its namespace) is enumerated, with
    the first docstring line as the summary and any `usage:` line as usage.

    This is a UX aid only -- it does not gate what `POST /api/gm/commands/run`
    will execute; the live `mod_only(...)` checks inside the command layer are
    the only real gate. Cached at `_cache` after the first build.
    """

    _cache = None

    @staticmethod
    def _arg_spec(spec):
        """Serialize one `Arg` declaration into a JSON-friendly dict.

        `type` is the converter's name (str/int/bool are the native ones;
        anything else is a custom converter and renders as a free-text field).
        Defaults and choices are normalized so they always survive json.dumps.
        """
        if spec.type is str:
            type_name = "str"
        elif spec.type is int:
            type_name = "int"
        elif spec.type is bool:
            type_name = "bool"
        else:
            type_name = getattr(spec.type, "__name__", str(spec.type))

        def _jsonable(value):
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            return str(value)

        return {
            "name": spec.name,
            "type": type_name,
            "required": bool(spec.required),
            "default": _jsonable(spec.default),
            "choices": [_jsonable(c) for c in spec.choices] if spec.choices else None,
            "rest": spec.rest,
            "variadic": spec.variadic,
            "help": spec.help,
        }

    @staticmethod
    def _permission(func):
        """Map a function's `mod_only` gate to a permission tier.

        No gate means public; `mod_only(area_owners=True)` is reachable by
        CMs, GMs, mods and system executors; `mod_only(hub_owners=True)` by
        GMs, mods and system executors; a bare `mod_only()` is mods only.
        """
        gate = getattr(func, "mod_only_gate", None)
        if gate is None:
            return "public"
        if gate == (True, False):
            return "area_owners"
        if gate == (False, True):
            return "hub_owners"
        if gate == (True, True):
            return "any_owner"
        return "mod_only"

    @classmethod
    def _describe(cls, name, func, module_name):
        doc = inspect.getdoc(func) or ""
        lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
        summary = lines[0] if lines else ""
        usage_lines = [ln for ln in lines if "usage:" in ln.lower()]
        prefix = "ooc_cmd_"
        display_name = name[len(prefix):] if name.startswith(prefix) else name
        return {
            "name": display_name,
            "module": module_name,
            "summary": summary,
            "usage": " ".join(usage_lines),
            "permission": cls._permission(func),
            "args": [cls._arg_spec(spec) for spec in getattr(func, "command_spec", ())],
        }

    @classmethod
    def _build(cls):
        groups = []
        for module in commands.submodules():
            module_name = module.__name__.split(".")[-1]
            names = getattr(module, "__all__", None)
            if names is None:
                names = [n for n in dir(module) if n.startswith("ooc_cmd_")]
            cmd_list = []
            for name in names:
                if not name.startswith("ooc_cmd_"):
                    continue
                func = getattr(module, name, None)
                if func is None:
                    continue
                cmd_list.append(cls._describe(name, func, module_name))
            cmd_list.sort(key=lambda c: c["name"])
            groups.append({"module": module_name, "commands": cmd_list})
        groups.sort(key=lambda g: g["module"])
        return groups

    @classmethod
    def to_groups(cls):
        if cls._cache is None:
            cls._cache = cls._build()
        return cls._cache

    @classmethod
    def to_flat(cls):
        """The whole catalog as one list of command dicts (each carrying its
        module name), preserving the per-module sort order."""
        out = []
        for group in cls.to_groups():
            out.extend(group["commands"])
        return out

    @classmethod
    def invalidate(cls):
        """Drop the cached catalog; called by `server.commands.reload()` (/refresh)."""
        cls._cache = None
