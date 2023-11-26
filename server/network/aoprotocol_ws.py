import asyncio
import logging

from websockets import ConnectionClosed

from server.network.aoprotocol import AOProtocol
from server.network.proxy_manager import ProxyManager
from server.exceptions import ClientError


class AOProtocolWS(AOProtocol):
    """A websocket wrapper around AOProtocol."""

    class WSTransport(asyncio.Transport):
        """A subclass of asyncio's Transport class to handle websocket connections."""

        def __init__(self, websocket):
            super().__init__()
            self.ws = websocket

        def get_extra_info(self, key, default=None):
            """Get extra info about the client.
            Usually used for getting the remote address. Overrides asyncio.Transport.get_extra_info.

            :param key: requested key
            :param default: default value if key is not found

            """
            # Anything that isn't the remote address is handled by the base class
            if key != "peername":
                return super().get_extra_info(key, default)

            # Remote address is a tuple of (ip, port), so just grab the IP
            remote_ip = self.ws.remote_address[0]

            headers = self.ws.request_headers
            if 'X-Forwarded-For' in headers:
                # This means the client claims to be behind a reverse proxy
                # However, we can't trust this information and need to check it against a whitelist
                # We need to check if the IP of the proxy itself is approved
                proxy_ip = remote_ip
                client_ip = headers['X-Forwarded-For']
                proxy_manager = ProxyManager.instance()
                if not proxy_manager.is_ip_authorized_as_proxy(proxy_ip):
                    msg = f"Unauthorized proxy detected. Proxy IP: {proxy_ip}. Client IP: {client_ip}."
                    # This means the request is coming from an unauthorized proxy, which is suspicious
                    logging.warning(
                        msg,
                        proxy_ip, client_ip)

                    ban_msg = f"BD#{msg}#%"

                    self.write(ban_msg.encode("utf-8"))
                    raise ClientError

                # The proxy is authorized, so we can trust the claimed client IP
                remote_ip = client_ip

            # Caller expects a tuple of (ip, port), so use the original source port
            return remote_ip, self.ws.remote_address[1]

        def write(self, message):
            """Write message to the socket. Overrides asyncio.Transport.write.

            :param message: message in bytes

            """
            message = message.decode("utf-8")
            asyncio.ensure_future(self.ws_try_writing_message(message))

        def close(self):
            """Disconnect the client by force. Overrides asyncio.Transport.close."""
            asyncio.ensure_future(self.ws.close())

        async def ws_try_writing_message(self, message):
            """
            Try writing the message if the client has not already closed
            the connection.
            """
            try:
                await self.ws.send(message)
            except ConnectionClosed:
                return

    def __init__(self, server, websocket):
        super().__init__(server)
        self.ws = websocket
        self.ws_connected = True

        self.ws_on_connect()

    def ws_on_connect(self):
        """Handle a new client connection."""
        self.connection_made(self.WSTransport(self.ws))

    async def ws_handle(self):
        try:
            data = await self.ws.recv()
            self.data_received(data)
        except Exception as exc:
            # Any event handled in data_received could raise any exception
            self.ws_connected = False
            self.connection_lost(exc)


def new_websocket_client(server):
    """
    Factory for creating a new WebSocket client.
    :param server: server object

    """

    async def func(websocket, _):
        client = AOProtocolWS(server, websocket)
        while client.ws_connected:
            await client.ws_handle()

    return func
