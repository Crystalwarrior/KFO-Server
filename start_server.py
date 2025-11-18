import os
import subprocess
import sys


# Install dependencies in case one is missing
def check_deps():
    py_version = sys.version_info
    if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 7):
        print("tsuserver3 requires at least Python 3.7! Your version: {}.{}".format(py_version.major, py_version.minor))
        sys.exit(1)

    try:
        import arrow
        import discord
        import geoip2
        import oyaml
        import pytimeparse
        import stun
        import websockets
    except ModuleNotFoundError:
        print("Installing dependencies for you...")
        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    "requirements.txt",
                ]
            )
            print("If an import error occurs after the installation, try restarting the server.")
        except subprocess.CalledProcessError:
            print("Couldn't install it for you, because you don't have pip, or another error occurred.")


def main():
    from server.tsuserver import TsuServer

    server = TsuServer()
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
