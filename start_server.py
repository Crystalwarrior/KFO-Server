import os

from server.kfoserver import KFOServer


def main():
    server = KFOServer()
    server.start()


if __name__ == "__main__":
    print("KFO-server - an Attorney Online server")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, closing server...")
    except SystemExit:
        if os.name == "nt":
            input("(Press Enter to exit)")
