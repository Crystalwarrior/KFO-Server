import sys
import logging
import traceback

import asyncio
import aiohttp
import stun

logger = logging.getLogger("debug")
stun_servers = [
    ("stun.l.google.com", 19302),
    ("global.stun.twilio.com", 3478),
    ("stun.voip.blackberry.com", 3478),
]

API_BASE_URL = "https://servers.aceattorneyonline.com"


class MasterServerClient:
    """Advertises information about this server to the masterserver."""

    def __init__(self, server):
        self.server = server
        self.interval = 60

    async def connect(self):
        """
        Connects to the server and sends server information periodically.

        This function establishes a connection to the server using the aiohttp library's
        ClientSession. It then enters a loop where it continuously sends server information
        using the `send_server_info` method. If a `ClientError` occurs while sending the
        information, it is logged as a connection error. Otherwise, if an unknown error
        occurs, it is logged as an unknown connection error. In both cases, the function
        sleeps for 5 seconds before retrying. Finally, the function sleeps for 60 seconds
        before sending the next server information.

        Parameters:
            self: The instance of the class.

        Returns:
            None
        """
        async with aiohttp.ClientSession() as http:
            while True:
                try:
                    await self.send_server_info(http)
                except aiohttp.ClientError:
                    # Masterserver is down or unreachable, may be temporary so log it as a warning
                    logger.warning("Failed to connect to the master server")
                except Exception:
                    # Unknown error occurred, log it as a hard error with full exception information
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    logger.error("Uncaught exception while advertising server to masterserver")
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                finally:
                    await asyncio.sleep(self.interval)

    def get_my_ip(self):
        """
        Get the external IP address using STUN servers.

        Returns:
            str: The external IP address.
        """
        for stun_ip, stun_port in stun_servers:
            nat_type, external_ip, _external_port = stun.get_ip_info(stun_host=stun_ip, stun_port=stun_port)
            if nat_type != stun.Blocked:
                return external_ip

        return None

    async def send_server_info(self, http: aiohttp.ClientSession):
        """
        Send server information to the specified HTTP client session.
        Usually being the masterserver.

        Parameters:
            http (aiohttp.ClientSession): The aiohttp client to send the server information to.

        Returns:
            None
        """
        cfg = self.server.config

        # Try to get the custom hostname
        f_ip = cfg.get("masterserver_custom_hostname")

        # If fails, try to get the external IP
        if not f_ip:
            f_ip = await asyncio.to_thread(self.get_my_ip)

        advertise_body = {
            "ip": f_ip,
            "port": cfg["port"],
            "name": cfg["masterserver_name"],
            "description": cfg["masterserver_description"],
            "players": self.server.player_count,
        }

        self.add_ws_info(advertise_body)

        async with http.post(f"{API_BASE_URL}/servers", json=advertise_body) as res:
            err_body = await res.text()
            try:
                res.raise_for_status()
            except aiohttp.ClientResponseError as err:
                logging.error("Got status=%s advertising %s: %s", err.status, advertise_body, err_body)

        logger.debug("Heartbeat to %s/servers", API_BASE_URL)

    # Helper to add websocket info to advertise_body
    def add_ws_info(self, advertise_body: dict) -> None:
        cfg = self.server.config

        if "use_websockets" not in cfg or not cfg["use_websockets"]:
            # Explicitly disabled, return
            return

        if "websocket_port" not in cfg or not cfg["websocket_port"]:
            # If we don't listen on a websocket port, don't advertise it
            return

        ws_port = cfg["websocket_port"]

        # Override if advertised_websocket_port is present and valid
        if "advertised_websocket_port" in cfg and cfg["advertised_websocket_port"]:
            ws_port = cfg["advertised_websocket_port"]

        advertise_body["ws_port"] = ws_port

        if "use_securewebsockets" in cfg and cfg["use_securewebsockets"]:
            if "secure_websocket_port" in cfg and cfg["secure_websocket_port"]:
                advertise_body["wss_port"] = cfg["secure_websocket_port"]
