import os
import shlex
from pathlib import Path


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

        client.send_ooc(arg)
        print(type(arg))
        print(arg)
        client.send_ooc("hi")

    def add_music(self, music):
        self.music.append(music)

    def get_music(self):
        return self.music

    def remove_music(self, music):
        self.music.remove(music)

    @staticmethod
    def load_help():
        helptext_path = script_dir / '../docs/cmd_music.txt'

        with open(helptext_path, 'r') as file:
            helptext = file.read()

        return helptext
