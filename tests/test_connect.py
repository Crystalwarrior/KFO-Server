import asyncio

from tests.mock.mocks import MockServer, make_protocol_factory


def test_client_can_connect_and_receive_handshake():
    """
    Spin up a tiny TCP server using AOProtocol and a minimal fake server,
    then connect with an asyncio client and assert we receive the initial
    NOENCRYPT handshake message sent by the server.
    """

    async def _run():
        mock_server = MockServer(timeout=1)

        loop = asyncio.get_running_loop()
        srv = await loop.create_server(make_protocol_factory(mock_server), "127.0.0.1", 0)

        try:
            host, port = srv.sockets[0].getsockname()[:2]
            reader, writer = await asyncio.open_connection(host, port)

            # The server should immediately send the decryptor/NOENCRYPT command
            data = await asyncio.wait_for(reader.readuntil(b"#%"), timeout=1.0)
            assert data.startswith(b"decryptor#NOENCRYPT")

            # Cleanly close client side
            writer.close()
            await writer.wait_closed()
        finally:
            srv.close()
            await srv.wait_closed()

    asyncio.run(_run())
