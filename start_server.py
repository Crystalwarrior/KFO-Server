import os
import shutil

from server.kfoserver import KFOServer


def main():
    if not os.path.exists("config"):
        print("Config folder not found, copying from config_sample...")
        shutil.copytree("config_sample", "config")

    server = KFOServer()
    server.start()


if __name__ == "__main__":
    print("KFO-Server - an Attorney Online server")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, closing server...")
    except SystemExit:
        if os.name == "nt":
            input("(Press Enter to exit)")
