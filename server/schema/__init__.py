"""
Declarative, single-source-of-truth schemas for things the GM panel (and, where
noted, the core command/scripting layers) expose to the web view.

These modules are deliberately LEAF modules: they import nothing from the rest
of ``server.*`` (only stdlib and ``server.exceptions``, itself a leaf), so
``server/area.py``, the ``server/commands`` package, ``server/scripting.py``
and ``server/web_view`` can all import them without circular imports.

The point of this package is to remove the "touch six or seven spots to add a
feature" problem: a field/property is declared once here, and every consumer
derives its list from the declaration.
"""

from server.schema.area_fields import (
    AREA_EDITABLE_FIELDS,
    AREA_FIELD_META,
    AREA_PREF_CM_ALLOWED,
    AREA_SCALAR_FIELDS,
    AREA_WRITE_STRATEGIES,
)
from server.schema.link_props import (
    LINK_PROPERTIES,
    LINK_PROPERTY_SCHEMA,
    LinkProp,
)

__all__ = [
    "AREA_EDITABLE_FIELDS",
    "AREA_FIELD_META",
    "AREA_PREF_CM_ALLOWED",
    "AREA_SCALAR_FIELDS",
    "AREA_WRITE_STRATEGIES",
    "LINK_PROPERTIES",
    "LINK_PROPERTY_SCHEMA",
    "LinkProp",
]
