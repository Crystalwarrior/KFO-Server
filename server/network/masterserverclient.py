import sys
import logging
import traceback

import asyncio
import aiohttp
import stun


logger = logging.getLogger("debug")
stun_servers = [
    ('stun.l.google.com', 19302),
    ('global.stun.twilio.com', 3478),
    ('stun.voip.blackberry.com', 3478),
]

API_BASE_URL = 'https://servers.aceattorneyonline.com'


class MasterServerClient:
    """Advertises information about this server to the master server."""

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
                    # Master server is down or unreachable, may be temporary so log it as a warning
                    logger.warning('Failed to connect to the master server')
                except Exception as err:
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
            nat_type, external_ip, _external_port = \
                stun.get_ip_info(stun_host=stun_ip, stun_port=stun_port)
            if nat_type != stun.Blocked:
                return external_ip

    async def send_server_info(self, http: aiohttp.ClientSession):
        """
        Send server information to the specified HTTP client session.
        Usually being the master server.

        Parameters:
            http (aiohttp.ClientSession): The aiohttp client to send the server information to.

        Returns:
            None
        """
        cfg = self.server.config

        # Try to get the custom hostname
        f_ip = cfg.get('masterserver_custom_hostname')

        # If fails, try to get the external IP
        if not f_ip:
            loop = asyncio.get_event_loop()
            f_ip = await loop.run_in_executor(None, self.get_my_ip)

        body = {
            'ip': f_ip,
            'port': cfg['port'],
            'name': cfg['masterserver_name'],
            'description': cfg['masterserver_description'],
            'players': self.server.player_count
        }

        if cfg['use_websockets']:
            body['ws_port'] = cfg['websocket_port']

        if 'use_securewebsockets' in cfg and cfg['use_securewebsockets']:
            if 'secure_websocket_port' in cfg:
                body['wss_port'] = cfg['secure_websocket_port']

        async with http.post(f'{API_BASE_URL}/servers', json=body) as res:
            err_body = await res.text()
            try:
                res.raise_for_status()
            except aiohttp.ClientResponseError as err:
                logging.error("Got status=%s advertising %s: %s", err.status, body, err_body)

        logger.debug('Heartbeat to %s/servers', API_BASE_URL)
