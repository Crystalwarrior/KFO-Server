import logging
import os
import shutil
from pathlib import Path

import pytest
import yaml


@pytest.fixture
async def test_server(tmp_path):
    """Real KFOServer in a temporary directory.

    Copies config_sample/ and migrations/ into tmp_path, creates
    storage/ and logs/, patches CWD, and yields a running server
    with a bound WebSocket port.

    Access the host/port via ``server._test_host`` and ``server._test_port``.
    """
    project_root = Path(__file__).resolve().parent.parent

    # 1. Copy config and migrations to tmp dir
    shutil.copytree(project_root / "config_sample", tmp_path / "config")
    shutil.copytree(project_root / "migrations", tmp_path / "migrations")
    (tmp_path / "storage").mkdir()
    (tmp_path / "logs").mkdir()

    # 2. Patch config to disable network features
    config_path = tmp_path / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    config["use_masterserver"] = False
    config["use_websockets"] = False  # We call serve_websocket() directly with port 0
    if "bridgebot" in config:
        config["bridgebot"]["enabled"] = False
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    # 3. chdir to tmp_path so KFOServer finds config/
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    # 4. Reset database singleton (gets fresh SQLite in tmp storage/)
    import server.database

    server.database._database_singleton = None

    # 5. Instantiate real server.
    from server.kfoserver import KFOServer

    server_instance = KFOServer()

    # 7. Start WebSocket server on a random port using the server's own method
    ws_server = await server_instance.serve_websocket("127.0.0.1", 0)
    host, port = list(ws_server.sockets)[0].getsockname()[:2]
    server_instance._test_host = host
    server_instance._test_port = port

    yield server_instance

    # Cleanup
    ws_server.close()
    await ws_server.wait_closed()
    os.chdir(original_cwd)
    server.database._database_singleton = None

    # Clear logging file handlers added during init
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
