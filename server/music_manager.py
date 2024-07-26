import os
import shlex
from pathlib import Path

from server.exceptions import ClientError, ServerError, ArgumentError, AreaError


script_dir = Path(os.path.dirname(os.path.realpath(__file__)))


class MusicManager:
    def __init__(self, area):
        # This is the area the music manager belongs to
        self.area = area
        self.music = []
        self.helptext = MusicManager.load_help()

    def handle_music_cmd(self, client, arg):
        args = shlex.split(arg)

        if len(args) < 1 or args[0] == "help":
            client.send_ooc(self.helptext)
            return

        subcmd = args[0]
        cmd_function_name = f"cmd_{subcmd}"
        if not hasattr(self, cmd_function_name):
            raise ClientError(f"Unknown subcommand {subcmd}. Use /music help for a list of commands.")

        cmd_function = getattr(self, cmd_function_name)
        cmd_function(client, args[1:])

    def cmd_showcurrent(self, client, arg):
        if len(arg) != 0:
            raise ArgumentError("This command has no arguments.")
        if client.area.music == "":
            raise ClientError("There is no music currently playing.")
        if client.is_mod:
            client.send_ooc(
                "The current music is '{}' and was played by {} ({}).".format(
                    client.area.music,
                    client.area.music_player,
                    client.area.music_player_ipid,
                )
            )
        else:
            client.send_ooc(
                "The current music is '{}' and was played by {}.".format(
                    client.area.music, client.area.music_player
                )
            )

    def cmd_playlast(self, client, arg):
        if len(arg) != 0:
            raise ArgumentError("This command has no arguments.")
        if client.area.music == "":
            raise ClientError("There is no music currently playing.")
        client.send_command(
            "MC",
            client.area.music,
            -1,
            "",
            client.area.music_looping,
            0,
            client.area.music_effects,
        )
        client.send_ooc(f"Playing track '{client.area.music}'.")

    @staticmethod
    def load_help():
        helptext_path = script_dir / '../docs/cmd_music.txt'

        with open(helptext_path, 'r') as file:
            helptext = file.read()

        return helptext
