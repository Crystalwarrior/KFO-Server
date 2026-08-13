"""Hardened yaml loading for untrusted, client-submitted GM panel content.

The GM panel runs on the same single asyncio event loop as the game server, so a
synchronous `yaml.safe_load()` of arbitrary client-submitted text must never be
allowed to take unbounded time/memory. None of the yaml kinds this API writes
has any legitimate use for YAML anchors/aliases, so `_BoundedSafeLoader` rejects
them outright, and also caps total composed nodes and nesting depth.
"""

import oyaml as yaml


_MAX_YAML_NODES = 200000
_MAX_YAML_DEPTH = 100


class _YamlTooComplex(yaml.YAMLError):
    """Raised by `_BoundedSafeLoader` when a document is rejected as too complex."""


class _BoundedSafeLoader(yaml.SafeLoader):
    """
    `yaml.SafeLoader` variant hardened for parsing arbitrary, untrusted,
    client-submitted YAML: rejects anchors/aliases, and aborts composition once
    more than `_MAX_YAML_NODES` nodes or `_MAX_YAML_DEPTH` levels are seen.
    """

    def compose_node(self, parent, index):
        if self.check_event(yaml.events.AliasEvent):
            raise _YamlTooComplex("YAML aliases ('*name') are not permitted here.")
        event = self.peek_event()
        if getattr(event, "anchor", None):
            raise _YamlTooComplex("YAML anchors ('&name') are not permitted here.")

        count = getattr(self, "_gm_node_count", 0) + 1
        self._gm_node_count = count
        if count > _MAX_YAML_NODES:
            raise _YamlTooComplex("YAML document is too complex (too many nodes).")

        depth = getattr(self, "_gm_depth", 0) + 1
        self._gm_depth = depth
        if depth > _MAX_YAML_DEPTH:
            raise _YamlTooComplex("YAML document is nested too deeply.")
        try:
            return super().compose_node(parent, index)
        finally:
            self._gm_depth -= 1


def _bounded_safe_load(content):
    """
    `yaml.safe_load()`, but using `_BoundedSafeLoader`. Raises `yaml.YAMLError`
    (including `_YamlTooComplex`) on invalid or rejected input; a raw
    `RecursionError` is converted into `_YamlTooComplex` so callers only ever
    catch one exception type for "reject this content".
    """
    try:
        return yaml.load(content, Loader=_BoundedSafeLoader)
    except RecursionError:
        raise _YamlTooComplex("YAML document is nested too deeply.")
