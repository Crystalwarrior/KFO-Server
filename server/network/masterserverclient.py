# KFO-Server, an Attorney Online server
#
# Copyright (C) 2020 Crystalwarrior <varsash@gmail.com>
#
# Derivative of tsuserver3, an Attorney Online server. Copyright (C) 2016 argoneus <argoneuscze@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import aiohttp
import stun
import time
from threading import Thread

import logging

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
                except aiohttp.ClientError as err:  # Connection error
                    logger.debug(
                        'Connection error occurred. (Couldn\'t reach the master server). Error: (%s)', err)

                    await asyncio.sleep(5)
                except Exception as err:  # Unknown error
                    logger.debug("Unknown connection error occurred on the master server. Error: (%s)", err)
                    await asyncio.sleep(5)
                finally:
                    await asyncio.sleep(60)

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
        loop = asyncio.get_event_loop()
        cfg = self.server.config

        # Try to get the custom hostname
        f_ip = cfg.get('masterserver_custom_hostname')

        # If fails, try to get the external IP
        if not f_ip:
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
        if cfg['use_securewebsockets']:
            body['wss_port'] = cfg['securewebsocket_port']

        async with http.post(f'{API_BASE_URL}/servers', json=body) as res:
            err_body = await res.text()
            try:
                res.raise_for_status()
            except aiohttp.ClientResponseError as err:
                logging.error("Got status=%s advertising %s: %s", err.status, body, err_body)

        logger.debug('Heartbeat to %s/servers', API_BASE_URL)
