import sys
import logging
import logging.handlers


def setup_logging(debug: bool = False):
    formatter = logging.Formatter(
        "[%(asctime)s][%(name)s][%(levelname)s] %(message)s")

    # Log to terminal (stdout)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stdout_handler)

    # Log to server.log
    serverlog_handler = logging.handlers.RotatingFileHandler(
        "logs/server.log", encoding="utf-8", maxBytes=1024 * 512
    )
    # The serverlog should never log debug messages
    serverlog_handler.setLevel(logging.INFO)
    serverlog_handler.setFormatter(formatter)
    logging.getLogger().addHandler(serverlog_handler)

    if debug:
        # Log to debug.log
        debuglog_handler = logging.handlers.RotatingFileHandler(
            "logs/debug.log", encoding="utf-8", maxBytes=1024 * 1024 * 4
        )
        debuglog_handler.setFormatter(formatter)
        logging.getLogger().addHandler(debuglog_handler)

    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


def parse_client_info(client):
    """Prepend information about a client to a log entry."""
    if client is None:
        return ""
    ipid = client.ip
    prefix = f"[{ipid:<15}][{client.id:<3}][{client.name}]"
    if client.is_mod:
        prefix += "[MOD]"
    return prefix
