import os
import logging
from pathlib import Path

import oyaml as yaml


script_dir = Path(os.path.dirname(os.path.realpath(__file__)))
logger = logging.getLogger("config")


# This class handles config options and should always reflect the config sample file in config_sample/config.yaml
class Config:
    # Loads in default values for config options
    def __init__(self):
        self.hostname = "<dollar>H"
        self.playerlimit = 100
        self.port = 27016
        self.local = False
        self.modpass = "mod"
        self.restartpass = "restart"
        self.motd = "Welcome to my server!"

        self.use_websockets = True
        self.websocket_port = 50001

        self.asset_url = "http://attorneyoffline.de/base/"

        self.use_masterserver = True

        self.masterserver_name = "My First Server"
        self.masterserver_description = "This is my flashy new server"

        self.timeout = 250

        self.packet_size = 1024

        self.block_repeat = True

        self.global_chat = True

        self.debug = False

        # Define nested config fields as nested classes
        self.music_change_floodguard = self.FloodGuard(3, 20, 180)
        self.wtce_floodguard = self.FloodGuard(5, 10, 1000)
        self.ooc_floodguard = self.FloodGuard(5, 5, 30)

        self.zalgo_tolerance = 3

        self.multiclient_limit = 16

        self.max_chars = 256
        self.max_chars_ic = 256

        self.bridgebot = self.Bridgebot()

        self.webhooks_enabled = False
        self.webhook_url = "https://example.com"

        self.modcall_webhook = self.ModcallWebook()

        self.kick_webhook = self.Webhook(True, "Kick", "")
        self.ban_webhook = self.Webhook(True, "Ban", "")
        self.unban_webhook = self.Webhook(True, "Unban", "")

    class FloodGuard:
        def __init__(self, times_per_interval, interval_length, mute_length):
            self.times_per_interval = times_per_interval
            self.interval_length = interval_length
            self.mute_length = mute_length

    class Bridgebot:
        def __init__(self):
            self.enabled = False
            self.token = "string1234"
            self.channel = "ao2-lobby"
            self.character = "Ponco"
            self.emote = "normal"
            self.pos = "jur"
            self.base_url = "http://www.example.com/base/"
            self.embed_emotes = False
            self.hub_id = 0
            self.area_id = 0
            self.prefix = "}}}[√Dis√] {"
            self.tickspeed = 0.25

    class ModcallWebook:
        def __init__(self):
            self.enabled = True
            self.username = "Modcall"
            self.avatar_url = ""
            self.ping_on_no_mods = False
            self.mod_role_id = ""

    class Webhook:
        def __init__(self, enabled, username, avatar_url):
            self.enabled = enabled
            self.username = username
            self.avatar_url = avatar_url

    def load_from_yaml(self, config_path: Path = None):
        if config_path is None:
            config_path = script_dir / "../config/config.yaml"

        if not config_path.exists():
            logger.warning("config.yaml not found, using default config")
            return

        with open(config_path, "r") as config_file:
            config = yaml.safe_load(config_file)

        # Set config options to values from config.yaml
        # TODO: Make this work recursively
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
