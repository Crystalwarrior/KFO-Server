import os


def main():
    from server.kfoserver import KFOServer

    KFOServer().start()


if __name__ == "__main__":
    print("KFO-Server - an Attorney Online server")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, closing server...")
    except SystemExit:
        # Truly idiotproof
        if os.name == "nt":
            input("(Press Enter to exit)")
