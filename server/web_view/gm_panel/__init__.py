"""GM Control Panel web application (package).

A separate aiohttp app (own port, own session cookie/store) that lets an
in-game GM micromanage their hub through a browser: areas as a graph, who's
present, characters/character-data, GM-scoped OOC commands, and the Automation
Demos system.

The public entry point is `GMPanelApp`; `tsuserver.py` imports it from here and
reads `.bridge` off the built app object. Everything else (sessions,
serializers, storage helpers, route handlers) is internal to this package --
see the individual modules.
"""

from server.web_view.gm_panel.app import GMPanelApp
from server.web_view.gm_panel.bridge import GMPanelBridge

__all__ = ["GMPanelApp", "GMPanelBridge"]
