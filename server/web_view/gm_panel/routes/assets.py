"""Asset config route: exposes the server's static-asset resolution config."""

from aiohttp import web


class AssetRoutes:
    """
    Exposes the server's static-asset resolution config so the frontend
    (`GMLocalContent`) can fall back to server-hosted assets (backgrounds, char
    icons, evidence images) when no local base folder/URL is configured or an
    item is missing from it.
    """

    def __init__(self, server, config):
        self._server = server
        self._config = config

    async def handle_config(self, request):
        server_config = getattr(self._server, "config", None) or {}
        asset_url = str(server_config.get("asset_url", "") or "")
        bg_thumb_base = str(self._config.get("background_thumb_base_url", "") or "")
        return web.json_response({
            "ok": True, "asset_url": asset_url, "bg_thumb_base": bg_thumb_base,
        })
