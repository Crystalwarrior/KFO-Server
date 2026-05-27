from unittest.mock import patch

import pytest

from tests.mock import MockClient


async def test_handshake(test_server):
    """Connect, perform the full handshake, and verify key state."""
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        info = await client.handshake()

        assert info["player_id"] is not None
        assert len(info["char_list"]) > 0
        assert "noencryption" in info["features"]


async def test_select_character(test_server):
    """After handshake, select a character and receive PV."""
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        await client.handshake()
        cmd, args = await client.select_character(0)

        assert cmd == "PV"
        assert client.char_id == 0


async def test_send_ic_message(test_server):
    """Select a character then send an IC message and receive the broadcast."""
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        await client.handshake()
        await client.select_character(0)

        await client.send_ic_message("Hello from test!")
        cmd, args = await client.recv_until("MS")

        # The broadcast MS packet should contain our message text at index 4
        assert args[4] == "Hello from test!"


@pytest.mark.xfail(
    reason=(
        "KFO's aoprotocol.data_received intentionally KKs and disconnects the "
        "client on any unhandled exception — see server/network/aoprotocol.py:76. "
        "Imported from czar where the protocol layer tolerates downstream errors."
    ),
    strict=True,
)
async def test_exception_does_not_disconnect(test_server):
    """A server-side exception during packet handling should not kick the client."""
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        await client.handshake()
        await client.select_character(0)

        # Find the server-side area for this client
        server_client = next(c for c in test_server.client_manager.clients if c.id == client.player_id)
        area = server_client.area

        # Patch area.send_ic to raise, simulating a server bug
        with patch.object(area, "send_ic", side_effect=RuntimeError("boom")):
            await client.send_ic_message("This will crash")
            await client.recv_all(timeout=0.2)

        # Client should still be connected — send another message and get a response
        await client.send_ooc_message("Still here?")
        msg = await client.recv_ooc(timeout=2.0)
        assert msg != ""
