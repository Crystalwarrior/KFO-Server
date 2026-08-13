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
    def _describe(name, func):
        doc = inspect.getdoc(func) or ""
        lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
        summary = lines[0] if lines else ""
        usage_lines = [ln for ln in lines if "usage:" in ln.lower()]
        prefix = "ooc_cmd_"
        display_name = name[len(prefix):] if name.startswith(prefix) else name
        return {
            "name": display_name,
            "summary": summary,
            "usage": " ".join(usage_lines),
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
                cmd_list.append(cls._describe(name, func))
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
    def invalidate(cls):
        """
        Cache-bust hook for a future cheap `server.commands.reload()` integration
        -- not currently wired to anything.
        """
        cls._cache = None
