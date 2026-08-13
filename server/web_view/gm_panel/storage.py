"""Shared helpers for the GM panel: command-output classification and the
generic GM-facing yaml file storage / path-safety layer.

These are plain module-level helpers (no classes, no server state) shared by the
route handlers. Kept dependency-light so serializers and routes can import them
freely.
"""

import os
import re

from aiohttp import web


# =============================================================================
# Command output classification
# =============================================================================

def _command_ok(output):
    return not any(str(line).startswith("[ERROR]") for line in output)


def _command_response(output):
    return web.json_response({"ok": _command_ok(output), "output": output})


# =============================================================================
# Generic GM-facing yaml file storage
# =============================================================================

# kind -> directory map, verified against the command bodies that actually
# read/write each of these. This is the ONLY place in the panel that knows
# these directories; every data-file endpoint goes through the helpers below
# instead of hand-building a path.
DATA_KIND_DIRS = {
    "hubs": "storage/hubs",
    "musiclists": "storage/musiclists",
    "charlists": "storage/charlists",
    "character_data": "storage/character_data",
    "evidence": "storage/evidence",
}

# Kinds that have a `read_only/` subdirectory of non-editable files.
DATA_KIND_READONLY_SUBDIR = frozenset(["hubs", "musiclists"])

# Kinds whose editable files are private to the GMs who created them and must
# NOT be listed to every GM with a session.
DATA_KIND_LIST_PUBLIC_ONLY = frozenset(["hubs"])

# Deliberately NOT `derelative()` -- a strict allowlist of the characters a
# panel-submitted file name SEGMENT may contain.
_DATA_NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,64}$")


def _split_data_name(name):
    """
    Validate a (possibly multi-segment, "/"-separated) panel-submitted data
    file name -- e.g. `"events/mystery"` -- and return its list of segments,
    or `None` if invalid.

    A valid name has 1-4 segments, EVERY segment matching `_DATA_NAME_RE`
    (which -- since it only allows `[A-Za-z0-9 _-]` -- already rejects an
    empty segment, `"."`, `".."`, any segment containing `/` itself, and any
    non-ASCII/unicode segment). No segment may literally be `"read_only"`.
    """
    if not isinstance(name, str) or name == "":
        return None
    segments = name.split("/")
    if not (1 <= len(segments) <= 4):
        return None
    for seg in segments:
        if not _DATA_NAME_RE.match(seg):
            return None
        if seg == "read_only":
            return None
    return segments


_MAX_DATA_FILE_BYTES = 256 * 1024


def _list_yaml_names(path):
    """List `*.yaml` filenames (minus extension) under `path`, sorted."""
    try:
        names = [f[:-5] for f in os.listdir(path) if f.lower().endswith(".yaml")]
        return sorted(names)
    except FileNotFoundError:
        return []


# A "subpath" data name may descend at most this many directory levels below a
# kind's own directory -- kept in lockstep with `_split_data_name`'s "1-4
# segments" rule.
_MAX_DATA_SUBDIR_DEPTH = 3


def _walk_data_files(base):
    """
    Recursively list `*.yaml` files under `base`, as relative paths WITHOUT the
    `.yaml` extension using "/" separators, sorted. Any directory literally
    named `read_only` is skipped entirely; recursion never follows symlinks and
    stops at `_MAX_DATA_SUBDIR_DEPTH` levels below `base`.
    """
    base = os.path.normpath(base)
    try:
        base_depth = base.count(os.sep)
    except Exception:
        return []
    results = []
    for root, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if d != "read_only"]
        depth = root.count(os.sep) - base_depth
        if depth >= _MAX_DATA_SUBDIR_DEPTH:
            dirs[:] = []
        rel_dir = os.path.relpath(root, base)
        for f in files:
            if not f.lower().endswith(".yaml"):
                continue
            stem = f[:-5]
            if rel_dir == ".":
                results.append(stem)
            else:
                results.append("/".join(rel_dir.split(os.sep) + [stem]))
    return sorted(results)


def _path_inside(root_realpath, candidate_path):
    """True iff `os.path.realpath(candidate_path)` is `root_realpath` or inside it."""
    real = os.path.realpath(candidate_path)
    return real == root_realpath or real.startswith(root_realpath + os.sep)


def _list_data_files(kind):
    """
    `[{"name": ..., "read_only": bool}, ...]` for every yaml file under `kind`'s
    directory, sorted editable-first then by name. Returns `None` for an unknown
    `kind`. Editable files are listed recursively; the `read_only/` tree stays
    flat/top-level.
    """
    base = DATA_KIND_DIRS.get(kind)
    if base is None:
        return None
    files = [{"name": n, "read_only": False} for n in _walk_data_files(base)]
    if kind in DATA_KIND_READONLY_SUBDIR:
        files += [
            {"name": n, "read_only": True}
            for n in _list_yaml_names(os.path.join(base, "read_only"))
        ]
    files.sort(key=lambda f: (f["read_only"], f["name"].lower()))
    return files


def _public_data_files(kind):
    """
    Like `_list_data_files`, but for kinds in `DATA_KIND_LIST_PUBLIC_ONLY` (hubs)
    only the `read_only` files are returned. Returns `None` for an unknown `kind`.
    """
    files = _list_data_files(kind)
    if files is None:
        return None
    if kind in DATA_KIND_LIST_PUBLIC_ONLY:
        return [f for f in files if f["read_only"]]
    return files


def _resolve_existing_data_path(kind, name):
    """
    Resolve `name` (validated via `_split_data_name`) to an existing yaml file
    under `kind`'s directory -- checking the `read_only/` subdirectory first for
    a single-segment `name`, then the editable directory (recursively) --
    verifying containment via `os.path.realpath`. Returns the real path, or
    `None` if `kind`/`name` are invalid or no such file exists.
    """
    base = DATA_KIND_DIRS.get(kind)
    if base is None:
        return None
    segments = _split_data_name(name)
    if segments is None:
        return None
    root = os.path.realpath(base)
    candidates = []
    if len(segments) == 1 and kind in DATA_KIND_READONLY_SUBDIR:
        candidates.append(os.path.join(base, "read_only", f"{segments[0]}.yaml"))
    rel_parts = segments[:-1] + [f"{segments[-1]}.yaml"]
    candidates.append(os.path.join(base, *rel_parts))
    for candidate in candidates:
        if _path_inside(root, candidate) and os.path.isfile(os.path.realpath(candidate)):
            return os.path.realpath(candidate)
    return None


def _safe_data_write_path(kind, name):
    """
    Resolve the EDITABLE-directory write target for `name` (validated via
    `_split_data_name`) under `kind`. Returns `(path, None)` on success, or
    `(None, error_code)` on failure. Never returns a path inside a `read_only/`
    subdirectory, and refuses to shadow an existing read-only file.
    """
    base = DATA_KIND_DIRS.get(kind)
    if base is None:
        return None, "unknown_kind"
    segments = _split_data_name(name)
    if segments is None:
        return None, "invalid_name"

    root = os.path.realpath(base)
    if len(segments) == 1 and kind in DATA_KIND_READONLY_SUBDIR:
        ro_root = os.path.realpath(os.path.join(base, "read_only"))
        ro_candidate = os.path.join(base, "read_only", f"{segments[0]}.yaml")
        if _path_inside(ro_root, ro_candidate) and os.path.isfile(os.path.realpath(ro_candidate)):
            return None, "read_only_exists"

    rel_parts = segments[:-1] + [f"{segments[-1]}.yaml"]
    path = os.path.join(base, *rel_parts)
    if not _path_inside(root, path):
        return None, "invalid_name"

    if len(segments) > 1:
        parent_dir = os.path.dirname(path)
        if not _path_inside(root, parent_dir):
            return None, "invalid_name"
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError:
            return None, "write_failed"

    return os.path.realpath(path), None


def _hub_data_gate_ok(session):
    """
    True iff the session's bound client may manage this hub's saved GM-facing
    data files. Replicates the `@mod_only(hub_owners=True)` gate every relevant
    command enforces, evaluated live so a GM demoted mid-session is rejected
    immediately.
    """
    client = session.bound_client
    hub = session.current_hub()
    return client.is_mod or client in hub.owners

