from tests.mock import MockClient


async def test_login_success(test_server):
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        await client.handshake()
        await client.send_ooc_message("/login mod")

        msg = await client.recv_ooc()
        assert msg == "Logged in as a moderator."


async def test_login_no_password_raises(test_server):
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        await client.handshake()
        await client.send_ooc_message("/login")

        msg = await client.recv_ooc()
        assert msg == "You must specify the password."


async def test_login_wrong_password_raises(test_server):
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        await client.handshake()
        await client.send_ooc_message("/login wrong")

        msg = await client.recv_ooc()
        assert msg == "Invalid password."


async def test_login_already_logged_in_raises(test_server):
    async with MockClient(test_server._test_host, test_server._test_port) as client:
        await client.handshake()
        await client.send_ooc_message("/login mod")
        await client.recv_ooc()  # consume success message

        await client.send_ooc_message("/login mod")
        msg = await client.recv_ooc()
        assert msg == "Already logged in."
