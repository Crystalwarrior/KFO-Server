import asyncio
from typing import Callable, Optional


class MockClient:
    """
    Minimal client object used by AOProtocol during the connection phase.

    It wraps the raw asyncio transport so tests can observe bytes written by
    the protocol via `send_command` and allows clean disconnection.
    """

    def __init__(self, transport):
        self.transport = transport
        # A tiny identifier string used only for logging in the protocol
        self.ipid = "test-ipid"
        # Optional references the real server might add; kept for parity
        self.server = None
        self.area = None

    def send_command(self, command: str, *args) -> None:
        """Encode and write an AO-style command to the transport.

        Example: send_command("decryptor", "NOENCRYPT") ->
        b"decryptor#NOENCRYPT#%"
        """
        msg = command
        if args:
            msg += "#" + "#".join(str(a) for a in args)
        msg += "#%"
        self.transport.write(msg.encode("utf-8"))

    # AOProtocol may call disconnect when timeouts happen
    def disconnect(self) -> None:
        try:
            self.transport.close()
        except Exception:
            pass


class MockClientManager:
    """Minimal client manager stub used by AOProtocol.

    Only the `new_client_preauth` method is used during handshake to apply
    a pre-auth limit; here we simply allow all connections.
    """

    def new_client_preauth(self, client: "MockClient") -> bool:  # noqa: ARG002
        return True


class MockServer:
    """Tiny server façade exposing only what AOProtocol touches in tests.

    Attributes
    - config: dict with at least `timeout` key
    - client_manager: object exposing `new_client_preauth`
    """

    def __init__(self, timeout: float = 1.0, client_factory: Optional[Callable] = None):
        self.config = {"timeout": timeout}
        self.client_manager = MockClientManager()
        self._client_factory = client_factory or (lambda transport: MockClient(transport))

    def new_client(self, transport):
        return self._client_factory(transport)

    def remove_client(self, client):  # noqa: ARG002
        # Not needed for initial handshake tests
        pass


def make_protocol_factory(server) -> Callable[[], object]:
    """Return a factory suitable for `loop.create_server`.

    Example usage:
        loop.create_server(make_protocol_factory(server), host, port)
    """
    from server.network.aoprotocol import AOProtocol

    return lambda: AOProtocol(server)
