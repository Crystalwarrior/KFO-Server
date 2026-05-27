import sys
import os


def check_deps():
    py_version = sys.version_info
    if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 11):
        print(
            "tsuserver3 requires at least Python 3.11! Your version: {}.{}".format(
                py_version.major, py_version.minor
            )
        )
        sys.exit(1)

    try:
        import oyaml  # noqa: F401
        import websockets  # noqa: F401
        import arrow  # noqa: F401
        import pytimeparse  # noqa: F401
        import geoip2  # noqa: F401
        import discord  # noqa: F401
        import stun  # noqa: F401
    except ModuleNotFoundError as err:
        print(f"Missing dependency: {err.name}.")
        print("Install dependencies with `uv sync` (see README.md).")
        sys.exit(1)


def main():
    from server.tsuserver import TsuServer3

    server = TsuServer3()
    server.start()


if __name__ == "__main__":
    print("tsuserver3 - an Attorney Online server")
    try:
        check_deps()
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, closing server...")
    except SystemExit:
        # Truly idiotproof
        if os.name == "nt":
            input("(Press Enter to exit)")
