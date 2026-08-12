from server import database
from server import commands
from server.evidence import EvidenceList
from server.exceptions import ClientError, AreaError, ArgumentError, ServerError
from server.constants import MusicEffect, ReportCardReason, derelative, censor
from server.timer import Timer
from server.script_runner import ScriptRunner, parse_demo_description
from server.remote_client import RemoteClient
from server.schema.link_props import LINK_PROPERTY_SCHEMA

from collections import OrderedDict

import asyncio
import random
import time
import arrow
import json

import oyaml as yaml  # ordered yaml
import os
import logging

logger = logging.getLogger("area")


class Area:
    """Represents a single instance of an area."""

    def __init__(self, area_manager, name):
        self.clients = set()
        self.invite_list = set()
        self.area_manager = area_manager
        self._name = name

        # Initialize prefs
        self._background = "default"
        self.background_suffix = ""
        self.overlay = ""
        self.pos_lock = []
        self.bg_lock = False
        self.overlay_lock = False
        self.evidence_mod = "FFA"
        self.can_cm = False
        self.locking_allowed = False
        self.iniswap_allowed = True
        self.showname_changes_allowed = True
        self.shouts_allowed = True
        self.jukebox = False
        self.abbreviation = self.abbreviate()
        self.non_int_pres_only = False
        self.locked = False
        self.muted = False
        self.blankposting_allowed = True
        self.blankposting_forced = False
        self.hp_def = 10
        self.hp_pro = 10
        self.doc = "No document."
        self.status = "IDLE"
        self.move_delay = 0
        self.hide_clients = False
        self.max_players = -1
        self.desc = ""
        self.music_ref = ""
        self.client_music = True
        self.replace_music = False
        self.ambience = ""
        self.can_dj = True
        self.music_locked = False
        self.hidden = False
        self.can_whisper = True
        self.can_wtce = True
        self.music_autoplay = False
        self.can_change_status = True
        self.use_backgrounds_yaml = False
        self.can_spectate = True
        self.can_getarea = True
        self.can_cross_swords = False
        self.can_scrum_debate = False
        self.can_panic_talk_action = False
        self.force_sneak = False
        # Whether the area is dark or not
        self.dark = False
        # The background to set when area's lights are turned off
        self.background_dark = "fxdarkness"
        # The pos to set when the area's lights are turned off
        self.pos_dark = "wit"
        # The desc to set when the area's lights are turned off
        self.desc_dark = "It's pitch black in here, you can't see a thing!"
        # Sends a message to the IC when changing areas
        self.passing_msg = False
        # Minimum time that has to pass before you can send another message
        self.msg_delay = 200
        # Whether to reveal evidence in all pos if it is presented
        self.present_reveals_evidence = True
        # Whether IC action messages (asterisk/color-3) are mirrored to OOC
        self.ooc_actions_enabled = True
        # /prefs end

        # DR minigames

        # CROSS SWORDS
        # The name of the song to play when minigame starts
        self.cross_swords_song_start = ""
        # The name of the song to play when minigame ends
        self.cross_swords_song_end = ""
        # The name of the song to play when minigame is conceded
        self.cross_swords_song_concede = ""
        # in seconds, 300s = 5m
        self.cross_swords_timer = 300

        # SCRUM DEBATE
        # The name of the song to play when minigame starts
        self.scrum_debate_song_start = ""
        # The name of the song to play when minigame ends
        self.scrum_debate_song_end = ""
        # The name of the song to play when minigame is conceded
        self.scrum_debate_song_concede = ""
        # in seconds, 300s = 5m. How much time is added on top of cross swords.
        self.scrum_debate_added_time = 300

        # PANIC TALK ACTION
        # The name of the song to play when minigame starts
        self.panic_talk_action_song_start = ""
        # The name of the song to play when minigame ends
        self.panic_talk_action_song_end = ""
        # The name of the song to play when minigame is conceded
        self.panic_talk_action_song_concede = ""
        # in seconds, 300s = 5m
        self.panic_talk_action_timer = 300
        # Cooldown in seconds, 300s = 5m
        self.minigame_cooldown = 300
        # Who's debating who
        self.red_team = set()
        self.blue_team = set()
        # Clients who cast votes
        self.votes_cast = set()
        # What percentage of valid voters needs to vote to force-end the minigame, rounded
        self.votes_percentage = 0.7
        # Minigame name
        self.minigame = ""
        # Minigame schedule
        self.minigame_schedule = None
        # /end

        self.old_muted = False
        self.old_invite_list = set()

        # original states for resetting the area after all CMs leave in a single area CM hub
        self.o_name = self._name
        self.o_abbreviation = self.abbreviation
        self.o_doc = self.doc
        self.o_desc = self.desc
        self.o_background = self._background

        self.music_looper = None
        self.next_message_time = 0
        self.judgelog = []
        self.music = ""
        self.music_player = ""
        self.music_player_ipid = -1
        self.music_looping = 0
        self.music_effects = 0
        self.evi_list = EvidenceList()
        self.testimony = []
        self.testimony_title = ""
        self.testimony_index = -1
        self.recording = False
        self.last_ic_message = None
        self.cards = dict()
        self.votes = dict()
        self.password = ""

        self.jukebox_votes = []
        self.jukebox_prev_char_id = -1

        self.music_list = []

        self._owners = set()
        self.afkers = []

        # Dictionary of dictionaries with further info, examine def link for more info
        self.links = {}

        # Timers ID 1 thru 20, (indexes 0 to 19 in area), timer ID 0 is reserved for hubs.
        self.timers = [Timer(x, area=self) for x in range(20)]

        # Demo playback is driven by a ScriptRunner bound to this area's
        # system executor client (see get_script_client).
        self.demo_runner = None
        self._script_client = None

        # Commands to call when certain triggers are fulfilled.
        self.triggers = {
            "join": "",  # User joins the area.
            "leave": "",  # User leaves the area.
        }

        # Mutable script variables for demo scripting (see docs/demo_scripting.md).
        self.variables = {}

        # Battle system stuff
        self.can_battle = True
        self.battle_started = False
        self.fighters = []
        self.num_selected_move = 0
        self.battle_guilds = {}

        # Battle system customization
        self.battle_paralysis_rate = 3
        self.battle_critical_rate = 15
        self.battle_critical_bonus = 1.5
        self.battle_bonus_malus = 1.5
        self.battle_poison_damage = 16
        self.battle_show_hp = True
        self.battle_min_multishot = 2
        self.battle_max_multishot = 5
        self.battle_burn_damage = 8
        self.battle_freeze_damage = 8
        self.battle_confusion_rate = 3
        self.battle_enraged_bonus = 2.25
        self.battle_stolen_stat = 10

        # multiple pair
        self.auto_pair = False
        self.auto_pair_max = "triple"
        self.auto_pair_cycle = False

        # medieval mode - transforms all messages in the area to Ye Olde English
        self.medieval_mode = False

        # list of areas to broadcast ic messages to
        self.broadcast_list = []

        # doorman vars
        self.doorman_call_time = 0

    @property
    def name(self):
        """Area's name string. Abbreviation is also updated according to this."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = value.strip()
        while "<num>" in self._name or "<percent>" in self._name:
            self._name = self._name.replace("<num>", "").replace("<percent>", "")
        self.abbreviation = self.abbreviate()

    @property
    def id(self):
        """Get area's index in the AreaManager's 'areas' list if present in its areas. Otherwise, return -1."""
        return self.area_manager.areas.index(self) if self in self.area_manager.areas else -1

    @property
    def server(self):
        """Area's server. Accesses AreaManager's 'server' property"""
        return self.area_manager.server

    @property
    def owners(self):
        """Area's owners. Also appends Game Masters (Hub Managers)."""
        return self.area_manager.owners | self._owners

    @property
    def background(self):
        """Current background of the area."""
        bg = self._background
        if self.dark:
            bg = self.background_dark
        return bg + self.background_suffix

    def trigger(self, trig, target):
        """Call the trigger's associated command through the system executor."""
        if isinstance(target, RemoteClient):
            return
        if target.hidden:
            return
        arg = self.triggers[trig]
        if arg == "":
            return
        self._run_trigger_command(arg, target)

    def trigger_evidence(self, evi, trig, target):
        """Call an evidence item's trigger (e.g. 'present') for a target."""
        if isinstance(target, RemoteClient):
            return
        if target.hidden:
            return
        arg = (evi.triggers or {}).get(trig, "")
        if arg == "":
            return
        self._run_trigger_command(arg, target)

    def _run_trigger_command(self, arg, target):
        """
        Run a trigger command through the area's system executor client.

        The executor is a headless participant, so no real player's state is
        hijacked and the trigger works regardless of which (if any) owners are
        currently online or in the area.
        """
        arg = (
            arg.replace("<cid>", str(target.id))
            .replace("<showname>", target.showname)
            .replace("<char>", target.char_name)
        )
        # Script context: a /demo run by this trigger can read who fired it
        # (see docs/demo_scripting.md). Values persist until the next trigger.
        self.variables["trigger_cid"] = target.id
        self.variables["trigger_showname"] = target.showname
        self.variables["trigger_char"] = target.char_name
        args = arg.split(" ")
        cmd = args.pop(0).lower()
        arg = " ".join(args)[:1024] if args else ""
        executor = self.get_script_client()
        executor.execute(cmd, arg)
        for msg in executor.output:
            if msg.startswith("[ERROR]"):
                self.broadcast_ooc(f"[Area {self.id}] {msg}")

    def get_script_client(self):
        """
        Get (creating if necessary) the system executor client for this area.

        The executor joins the area as a headless participant, so commands
        executed on it (`client.area`, `client.area.area_manager`,
        `area.owners`, `@mod_only` gates via `is_gm`) behave as if a real
        owner ran them -- without depending on one being online. It is not a
        mod: pure-mod commands are denied.

        Its authority mirrors the hub's ownership model. In GM-capable hubs
        (`can_gm`) it is added to the hub's GM owner set, so automation can
        use GM commands (e.g. the hub-wide `/timer 0`). In claim-only hubs
        (e.g. KFO Hub 0, where only areas can be claimed) it is added to the
        area's CM owner set instead, so a CM-set automation script acts as an
        area owner and can never escalate to GM power. It is added directly
        (not via `add_owner`, which broadcasts and hides the client) because
        many command bodies check the owner sets themselves rather than going
        through the `@mod_only` decorator.
        """
        if self._script_client is None:
            can_gm = self.area_manager.can_gm
            self._script_client = RemoteClient(self.server, is_mod=False, name="[SCRIPT]", is_gm=can_gm)
            self._script_client.is_automation = True
            self._script_client.join_area(self)
            if can_gm:
                self.area_manager.owners.add(self._script_client)
            else:
                self._owners.add(self._script_client)
        elif self._script_client.area is not self:
            # A GM-level executor may have been moved to another area (e.g. by
            # /area_kick). Pull it back to the area that owns it so the demo or
            # trigger runs against the correct area.
            self._script_client.join_area(self)
        return self._script_client

    def abbreviate(self):
        """Abbreviate our name."""
        if self.name.lower().startswith("courtroom"):
            return "CR" + self.name.split()[-1]
        elif self.name.lower().startswith("area"):
            return "A" + self.name.split()[-1]
        elif len(self.name.split()) > 1:
            return "".join(item[0].upper() for item in self.name.split())
        elif len(self.name) > 3:
            return self.name[:3].upper()
        else:
            return self.name.upper()

    def load(self, area):
        self._name = area["area"]
        self.o_name = self._name
        self.o_abbreviation = self.abbreviation
        _pos_lock = ""
        # Legacy KFO support.
        # We gotta fix the sins of our forefathers
        if "poslock" in area:
            _pos_lock = area["poslock"].split(" ")
        if "bglock" in area:
            self.bg_lock = area["bglock"]
        if "accessible" in area:
            self.links.clear()
            for link in [s for s in str(area["accessible"]).split(" ")]:
                self.link(link)

        if "is_locked" in area:
            self.locked = False
            self.muted = False
            if area["is_locked"] == "SPECTATABLE":
                self.muted = True
            elif area["is_locked"] == "LOCKED":
                self.locked = True

        if "background" in area:
            self._background = area["background"]
            self.o_background = self._background
        if "background_suffix" in area:
            self.background_suffix = area["background_suffix"]
        if "overlay" in area:
            self.overlay = area["overlay"]
        if "bg_lock" in area:
            self.bg_lock = area["bg_lock"]
        if "overlay_lock" in area:
            self.overlay_lock = area["overlay_lock"]
        if "pos_lock" in area:
            _pos_lock = area["pos_lock"].split(" ")

        if len(_pos_lock) > 0:
            self.pos_lock.clear()
            for pos in _pos_lock:
                pos = pos.lower()
                if pos != "none" and not (pos in self.pos_lock):
                    self.pos_lock.append(pos.lower())

        if "evidence_mod" in area:
            self.evidence_mod = area["evidence_mod"]
        if "can_cm" in area:
            self.can_cm = area["can_cm"]
        if "locking_allowed" in area:
            self.locking_allowed = area["locking_allowed"]
        if "iniswap_allowed" in area:
            self.iniswap_allowed = area["iniswap_allowed"]
        if "showname_changes_allowed" in area:
            self.showname_changes_allowed = area["showname_changes_allowed"]
        if "shouts_allowed" in area:
            self.shouts_allowed = area["shouts_allowed"]
        if "jukebox" in area:
            self.jukebox = area["jukebox"]
        if "abbreviation" in area:
            self.abbreviation = area["abbreviation"]
        else:
            self.abbreviation = self.abbreviate()
        if "non_int_pres_only" in area:
            self.non_int_pres_only = area["non_int_pres_only"]
        if "locked" in area:
            self.locked = area["locked"]
        if "muted" in area:
            self.muted = area["muted"]
        if "blankposting_allowed" in area:
            self.blankposting_allowed = area["blankposting_allowed"]
        if "blankposting_forced" in area:
            self.blankposting_forced = area["blankposting_forced"]
        if "hp_def" in area:
            self.hp_def = area["hp_def"]
        if "hp_pro" in area:
            self.hp_pro = area["hp_pro"]
        if "doc" in area:
            self.doc = area["doc"]
            self.o_doc = self.doc
        if "status" in area:
            self.status = area["status"]
        if "move_delay" in area:
            self.move_delay = area["move_delay"]
        if "hide_clients" in area:
            self.hide_clients = area["hide_clients"]
        if "music_autoplay" in area:
            self.music_autoplay = area["music_autoplay"]
            if self.music_autoplay and "music" in area:
                self.music = area["music"]
                self.music_effects = area["music_effects"]
                self.music_looping = area["music_looping"]
        if "max_players" in area:
            self.max_players = area["max_players"]
        if "desc" in area:
            self.desc = area["desc"]
            self.o_desc = self.desc
        if "music_ref" in area:
            self.music_ref = area["music_ref"]
            if self.music_ref == "":
                self.clear_music()
        if self.music_ref != "":
            if os.path.isfile(f"storage/musiclists/read_only/{self.music_ref}.yaml"):
                self.load_music(f"storage/musiclists/read_only/{self.music_ref}.yaml")
            else:
                self.load_music(f"storage/musiclists/{self.music_ref}.yaml")

        if "client_music" in area:
            self.client_music = area["client_music"]
        if "replace_music" in area:
            self.replace_music = area["replace_music"]
        if "ambience" in area:
            self.ambience = area["ambience"]
        if "can_dj" in area:
            self.can_dj = area["can_dj"]
        if "music_locked" in area:
            self.music_locked = area["music_locked"]
        if "hidden" in area:
            self.hidden = area["hidden"]
        if "can_whisper" in area:
            self.can_whisper = area["can_whisper"]
        if "can_wtce" in area:
            self.can_wtce = area["can_wtce"]
        if "can_change_status" in area:
            self.can_change_status = area["can_change_status"]
        if "use_backgrounds_yaml" in area:
            self.use_backgrounds_yaml = area["use_backgrounds_yaml"]
        if "can_spectate" in area:
            self.can_spectate = area["can_spectate"]
        if "can_getarea" in area:
            self.can_getarea = area["can_getarea"]
        if "can_cross_swords" in area:
            self.can_cross_swords = area["can_cross_swords"]
        if "can_scrum_debate" in area:
            self.can_scrum_debate = area["can_scrum_debate"]
        if "can_panic_talk_action" in area:
            self.can_panic_talk_action = area["can_panic_talk_action"]
        if "cross_swords_song_start" in area:
            self.cross_swords_song_start = area["cross_swords_song_start"]
        if "cross_swords_song_end" in area:
            self.cross_swords_song_end = area["cross_swords_song_end"]
        if "cross_swords_song_concede" in area:
            self.cross_swords_song_concede = area["cross_swords_song_concede"]
        if "scrum_debate_song_start" in area:
            self.scrum_debate_song_start = area["scrum_debate_song_start"]
        if "scrum_debate_song_end" in area:
            self.scrum_debate_song_end = area["scrum_debate_song_end"]
        if "scrum_debate_song_concede" in area:
            self.scrum_debate_song_concede = area["scrum_debate_song_concede"]
        if "panic_talk_action_song_start" in area:
            self.panic_talk_action_song_start = area["panic_talk_action_song_start"]
        if "panic_talk_action_song_end" in area:
            self.panic_talk_action_song_end = area["panic_talk_action_song_end"]
        if "panic_talk_action_song_concede" in area:
            self.panic_talk_action_song_concede = area["panic_talk_action_song_concede"]
        if "force_sneak" in area:
            self.force_sneak = area["force_sneak"]
        if "password" in area:
            self.password = area["password"]
        if "dark" in area:
            self.dark = area["dark"]
        if "background_dark" in area:
            self.background_dark = area["background_dark"]
        if "pos_dark" in area:
            self.pos_dark = area["pos_dark"]
        if "desc_dark" in area:
            self.desc_dark = area["desc_dark"]
        if "passing_msg" in area:
            self.passing_msg = area["passing_msg"]
        if "msg_delay" in area:
            self.msg_delay = area["msg_delay"]
        if "present_reveals_evidence" in area:
            self.present_reveals_evidence = area["present_reveals_evidence"]
        if "ooc_actions_enabled" in area:
            self.ooc_actions_enabled = area["ooc_actions_enabled"]

        if "evidence" in area and len(area["evidence"]) > 0:
            self.evi_list.evidences.clear()
            self.evi_list.import_evidence(area["evidence"])
            self.broadcast_evidence_list()

        if "links" in area and len(area["links"]) > 0:
            self.links.clear()
            for key, value in area["links"].items():
                # Only forward the fields the schema declares, so a new link
                # property is read here automatically and any unknown/legacy
                # YAML key is ignored (matching the old per-field behaviour).
                kwargs = {
                    prop.name: value[prop.name]
                    for prop in LINK_PROPERTY_SCHEMA
                    if prop.name in value
                }
                self.link(key, **kwargs)

        # Update the clients in that area
        if self.dark:
            self.change_background(self.background_dark, overlay=self.overlay)
        else:
            self.change_background(self._background, overlay=self.overlay)
        self.change_hp(1, self.hp_def)
        self.change_hp(2, self.hp_pro)
        if self.ambience:
            self.set_ambience(self.ambience)
        if self.music_autoplay:
            for client in self.clients:
                if self.music != client.playing_audio[0]:
                    client.send_command("MC", self.music, -1, "", self.music_looping, 0, self.music_effects)

        if "can_battle" in area:
            self.can_battle = area["can_battle"]

        if "auto_pair" in area:
            self.auto_pair = area["auto_pair"]
        if "auto_pair_max" in area:
            self.auto_pair_max = area["auto_pair_max"]
        if "auto_pair_cycle" in area:
            self.auto_pair_cycle = area["auto_pair_cycle"]

    def save(self):
        area = OrderedDict()
        area["area"] = self.name
        area["background"] = self._background
        area["background_suffix"] = self.background_suffix
        area["overlay"] = self.overlay
        area["pos_lock"] = "none"
        if len(self.pos_lock) > 0:
            area["pos_lock"] = " ".join(map(str, self.pos_lock))
        area["bg_lock"] = self.bg_lock
        area["overlay_lock"] = self.overlay_lock
        area["evidence_mod"] = self.evidence_mod
        area["can_cm"] = self.can_cm
        area["locking_allowed"] = self.locking_allowed
        area["iniswap_allowed"] = self.iniswap_allowed
        area["showname_changes_allowed"] = self.showname_changes_allowed
        area["shouts_allowed"] = self.shouts_allowed
        area["jukebox"] = self.jukebox
        area["abbreviation"] = self.abbreviation
        area["non_int_pres_only"] = self.non_int_pres_only
        area["locked"] = self.locked
        area["muted"] = self.muted
        area["blankposting_allowed"] = self.blankposting_allowed
        area["blankposting_forced"] = self.blankposting_forced
        area["hp_def"] = self.hp_def
        area["hp_pro"] = self.hp_pro
        area["doc"] = self.doc
        area["status"] = self.status
        area["move_delay"] = self.move_delay
        area["hide_clients"] = self.hide_clients
        area["music_autoplay"] = self.music_autoplay
        area["max_players"] = self.max_players
        area["desc"] = self.desc
        if self.music_ref != "":
            area["music_ref"] = self.music_ref
            area["replace_music"] = self.replace_music
        area["client_music"] = self.client_music
        if self.music_autoplay:
            area["music"] = self.music
            area["music_effects"] = self.music_effects
            area["music_looping"] = self.music_looping
        area["ambience"] = self.ambience
        area["can_dj"] = self.can_dj
        area["music_locked"] = self.music_locked
        area["hidden"] = self.hidden
        area["can_whisper"] = self.can_whisper
        area["can_wtce"] = self.can_wtce
        area["can_change_status"] = self.can_change_status
        area["use_backgrounds_yaml"] = self.use_backgrounds_yaml
        area["can_spectate"] = self.can_spectate
        area["can_getarea"] = self.can_getarea
        area["can_cross_swords"] = self.can_cross_swords
        area["can_scrum_debate"] = self.can_scrum_debate
        area["can_panic_talk_action"] = self.can_panic_talk_action
        area["cross_swords_song_start"] = self.cross_swords_song_start
        area["cross_swords_song_end"] = self.cross_swords_song_end
        area["cross_swords_song_concede"] = self.cross_swords_song_concede
        area["scrum_debate_song_start"] = self.scrum_debate_song_start
        area["scrum_debate_song_end"] = self.scrum_debate_song_end
        area["scrum_debate_song_concede"] = self.scrum_debate_song_concede
        area["panic_talk_action_song_start"] = self.panic_talk_action_song_start
        area["panic_talk_action_song_end"] = self.panic_talk_action_song_end
        area["panic_talk_action_song_concede"] = self.panic_talk_action_song_concede
        area["force_sneak"] = self.force_sneak
        area["password"] = self.password
        area["dark"] = self.dark
        area["background_dark"] = self.background_dark
        area["pos_dark"] = self.pos_dark
        area["desc_dark"] = self.desc_dark
        area["passing_msg"] = self.passing_msg
        area["msg_delay"] = self.msg_delay
        area["present_reveals_evidence"] = self.present_reveals_evidence
        area["ooc_actions_enabled"] = self.ooc_actions_enabled
        if len(self.evi_list.evidences) > 0:
            area["evidence"] = self.evi_list.export_evidence()
        if len(self.links) > 0:
            area["links"] = self.links
        area["can_battle"] = self.can_battle
        area["auto_pair"] = self.auto_pair
        area["auto_pair_max"] = self.auto_pair_max
        area["auto_pair_cycle"] = self.auto_pair_cycle
        return area

    def play_client_ambience(self, client):
        if client.software == "DRO":
            # DRO packet
            client.send_command(
                "area_ambient",
                # for compatibility with the KFO method, navigate out of sounds/ambience into sounds/music
                "../music/" + self.ambience,
            )
        else:
            # AO packet
            if self.ambience != client.playing_audio[1]:
                # Play the ambience
                client.send_command(
                    "MC",
                    self.ambience,
                    -1,
                    "",
                    1,
                    1,
                    int(MusicEffect.FADE_OUT | MusicEffect.FADE_IN | MusicEffect.SYNC_POS),
                )

    def new_client(self, client):
        """Add a client to the area."""
        self.clients.add(client)
        # Client not fully initialized yet. The rest will be handled when the client is done loading.
        if client.char_id is None:
            return
        database.log_area("area.join", client, self)
        self.update_client(client)
        bridge = getattr(self.server, "gm_panel_bridge", None)
        if bridge is not None:
            bridge.on_client_present(client, self)

    def update_client(self, client):
        """Update the client with the relevant information about the area. Does not care if the client loaded in yet or not."""
        # Autoplay music
        if self.music_autoplay and self.music != client.playing_audio[0]:
            client.send_command("MC", self.music, -1, "", self.music_looping, 0, self.music_effects)

        # Update the timers for the client
        self.update_timers(client)

        # Update ambience
        self.play_client_ambience(client)

        # Make sure their theme variation is correct
        self.area_manager.update_subtheme(client)

        # Update their player list information
        if not client.hidden and not client.sneaking:
            self.broadcast_player_list()
        else:
            self.broadcast_player_list_to_target(client)

    def update_judge_buttons(self, client):
        # Judge buttons are client-sided by default.
        jd = -1
        # This area won't let us use judge buttons unless we have privileges.
        if not self.can_wtce:
            # We can't use judge buttons, unless...
            jd = 0

        if client in self.owners or client in self.area_manager.owners or client.is_mod:
            # We are a CM, Mod or a GM! Give us judge buttons at all times!
            jd = 1
        if not client.can_wtce:
            # aw man we were muted by a mod we can't use wtce period :(
            jd = 0
        client.send_command("JD", jd)

    def update_timers(self, client, running_only=False):
        """Update the timers for the target client"""
        # this client didn't even pick char yet
        if client.char_id is None:
            return

        # Hub timers
        timer = client.area.area_manager.timer
        if timer.set:
            current_time = timer.static
            if timer.started:
                current_time = timer.target - arrow.get()
            int_time = int(current_time.total_seconds()) * 1000
            client.send_timer_set_time(0, int_time, timer.started)
        elif not running_only:
            client.send_timer_set_time(0, None, False)

        # Area timers
        for timer_id, timer in enumerate(self.timers):
            # Send static time if applicable
            if timer.set:
                current_time = timer.static
                if timer.started:
                    current_time = timer.target - arrow.get()
                int_time = int(current_time.total_seconds()) * 1000
                client.send_timer_set_time(timer_id + 1, int_time, timer.started)
            elif not running_only:
                client.send_timer_set_time(timer_id + 1, None, False)

    def remove_client(self, client):
        """Remove a disconnected client from the area."""
        if client.hidden_in is not None:
            client.hide(False, hidden=True)
        if self.area_manager.single_cm:
            # Remove their owner status due to single_cm pref. remove_owner will unlock the area if they were the last CM.
            if client in self._owners:
                self.remove_owner(client)
                client.send_ooc("You can only be a CM of a single area in this hub.")
        # Trigger this routine only if a non-privileged client left the area, and there are no GMs in this hub.
        if self.locking_allowed and len(self.real_cms()) <= 0 and len(self.area_manager.real_owners()) <= 0:
            # Since anyone can lock/unlock, unlock if we were the last client in this area and it was locked.
            if len(self.clients) - 1 <= 0:
                if self.locked:
                    self.unlock()
        self.trigger("leave", client)
        if client in self.clients:
            self.clients.remove(client)
        if client in self.afkers:
            self.afkers.remove(client)
            self.server.client_manager.toggle_afk(client)
        if self.jukebox:
            self.remove_jukebox_vote(client, True)
        if len(self.clients) == 0:
            self.change_status("IDLE")
        if client.char_id is not None:
            database.log_area("area.leave", client, self)
        if not client.hidden:
            self.area_manager.send_arup_players()
        if not client.hidden and not client.sneaking:
            self.broadcast_player_list()
        else:
            self.broadcast_player_list_to_target(client)

        # Battle system
        if client in client.area.fighters:
            if client.area.battle_started:
                client.battle.current_client = None
            else:
                client.area.fighters.remove(client)
                if client.battle.guild is not None:
                    guild = client.battle.guild
                    client.battle.guild = None
                    client.area.battle_guilds[guild].remove(client)
                if client.battle.selected_move != -1:
                    client.area.num_selected_move += -1
            client.area.send_ic(
                msg=f"~{client.battle.fighter}~ disconnected",
                anim=client.last_sprite,
                color=3,
                offset_pair=100,
            )

        # Update everyone's available characters list
        # Commented out due to potentially causing clientside lag...
        # self.send_command('CharsCheck',
        #                     *client.get_available_char_list())

        bridge = getattr(self.server, "gm_panel_bridge", None)
        if bridge is not None:
            bridge.on_client_absent(client, self)

    def unlock(self):
        """Mark the area as unlocked."""
        self.locked = False
        self.area_manager.send_arup_lock()

    def lock(self):
        """Mark the area as locked."""
        self.locked = True
        self.area_manager.send_arup_lock()

    def mute(self):
        """Mute the area."""
        self.muted = True
        self.invite_list.clear()
        self.area_manager.send_arup_lock()

    def unmute(self):
        """Unmute the area."""
        self.muted = False
        self.invite_list.clear()
        self.area_manager.send_arup_lock()

    def link(self, target, **kwargs):
        """
        Sets up a one-way connection between this area and targeted area.
        Returns the link dictionary.

        The link dict's field names and defaults are declared once in
        `server/schema/link_props.py` (the single source of truth); each
        keyword argument overrides the matching field's default, and a new
        link property added to that schema is included here automatically.

        :param target: the targeted Area ID to connect
        :param kwargs: per-property overrides (see LINK_PROPERTY_SCHEMA names)
        """
        link = {}
        for prop in LINK_PROPERTY_SCHEMA:
            default = prop.default
            if isinstance(default, list):
                default = list(default)
            link[prop.name] = kwargs.get(prop.name, default)
        self.links[str(target)] = link
        return link

    def send_seethrough_presence(self, client):
        """
        Send `client` an automatic presence peek for every area its
        see-through links point to. Runs when the client arrives in this area;
        shows who is in the target areas (presence only, no IC relay).
        """
        if client.blinded:
            return
        for target_id, link in self.links.items():
            if not link.get("seethrough", False):
                continue
            try:
                target = self.area_manager.get_area_by_id(int(target_id))
            except (ValueError, AreaError):
                continue
            if target == self or target.dark or not target.can_getarea:
                continue
            present = sorted(
                (c.showname for c in target.clients if not c.hidden and c not in target.owners and not c.is_mod),
                key=lambda s: s.lower(),
            )
            if len(present) == 0:
                presence = "There's nobody."
            elif len(present) == 1:
                presence = f"There's {present[0]}."
            else:
                presence = "There's " + ", ".join(present[:-1]) + f" and {present[-1]}."
            client.send_ooc(f"👁 [{target.id}] {target.name}: {presence}")

    def unlink(self, target):
        try:
            del self.links[str(target)]
        except KeyError:
            raise AreaError(f"Link {target} does not exist in Area {self.name}!")

    def is_char_available(self, char_id):
        """
        Check if a character is available for use.
        Area Owners occupying a character is ignored as a condition.
        :param char_id: character ID
        """
        for c in self.clients:
            if char_id == c.char_id and c not in self.owners:
                return False
        return True

    def get_rand_avail_char_id(self):
        """Get a random available character ID."""
        avail_set = set(range(len(self.area_manager.char_list))) - {x.char_id for x in self.clients}
        if len(avail_set) == 0:
            raise AreaError("No available characters.")
        return random.choice(tuple(avail_set))

    def send_command(self, cmd, *args):
        """
        Broadcast an AO-compatible command to all clients in the area.
        """
        for c in self.clients:
            c.send_command(cmd, *args)

    def send_owner_command(self, cmd, *args):
        """
        Send an AO-compatible command to all owners of the area
        that are not currently in the area.
        """
        for c in self.owners:
            if c in self.clients:
                continue
            if c.remote_listen == 3 or (cmd == "CT" and c.remote_listen == 2) or (cmd == "MS" and c.remote_listen == 1):
                c.send_command(cmd, *args)

    def send_owner_ic(self, bg, cmd, *args):
        """
        Send an IC message to all owners of the area
        that are not currently in the area, with the specified bg.
        """
        for c in self.owners:
            if c in self.clients:
                continue
            if c.remote_listen == 3 or (cmd == "MS" and c.remote_listen == 1):
                # Make sure the correct listen BG displays
                if c.area.background != bg:
                    c.send_command("BN", bg, "", "", 0)
                c.send_command(cmd, *args)

    def send_timer_set_time(self, timer_id=None, new_time=None, start=False):
        """Broadcast a timer to all clients in this area."""
        for c in self.clients:
            c.send_timer_set_time(timer_id, new_time, start)

    def broadcast_ooc(self, msg, exclude_list=[], relay_seethrough=False, exclude_seethrough_area=None):
        """
        Broadcast an OOC message to all clients in the area.
        :param msg: message
        """
        for c in self.clients:
            if c in exclude_list:
                continue
            c.send_command("CT", self.server.config["hostname"], msg, "1")
        self.send_owner_command("CT", f"[{self.id}]" + self.server.config["hostname"], msg, "1")
        if relay_seethrough:
            # Clients in areas with a see-through link to this area watch its
            # passing (presence) messages without being in it. The area on the
            # other side of the move is skipped: its users just saw the mover
            # leave/arrive, so the relayed message is redundant for them.
            for area in self.area_manager.areas:
                if area is exclude_seethrough_area:
                    continue
                link = area.links.get(str(self.id))
                if link is not None and link.get("seethrough", False):
                    for c in area.clients:
                        if c in exclude_list:
                            continue
                        # already remote listening, prevents spam
                        if c in area.owners and (c.remote_listen == 3 or c.remote_listen == 2):
                            continue
                        c.send_command("CT", f"[{self.id}] {self.name}:", msg, "1")
        # Discord Bridgebot
        if (
            "bridgebot" in self.server.config
            and self.server.config["bridgebot"]["enabled"]
            and self.server.bridgebot
            and self.area_manager.id == self.server.bridgebot.hub_id
            and self.id == self.server.bridgebot.area_id
        ):
            if "ooc_system" in self.server.config["bridgebot"] and self.server.config["bridgebot"]["ooc_system"]:
                self.server.bridgebot.queue_message(self.server.config["hostname"], msg)

    def broadcast_action(self, client, msg):
        """
        Broadcast an Action message to all clients in the area who are listening to actions.
        :param msg: message
        """
        if not self.ooc_actions_enabled:
            return
        cmd = "CT"
        msg = f"[❗] [{client.id}] {client.showname} action:\n{msg}"
        for c in self.clients:
            if not c.ooc_actions:
                continue
            c.send_command(cmd, self.server.config["hostname"], msg, "1")

        for c in self.owners:
            if c in self.clients:
                continue
            if not c.ooc_actions:
                continue
            if c.remote_listen == 3 or c.remote_listen == 2:
                c.send_command(cmd, f"[{self.id}]" + self.server.config["hostname"], msg, "1")

    def send_ic(
        self,
        client=None,
        msg_type="1",
        pre=0,
        folder="",
        anim="",
        msg="",
        pos="",
        sfx="",
        emote_mod=0,
        cid=-1,
        sfx_delay=0,
        button=0,
        evidence=[0],
        flip=0,
        ding=0,
        color=0,
        showname="",
        charid_pair=-1,
        other_folder="",
        other_emote="",
        offset_pair=0,
        other_offset=0,
        other_flip=0,
        nonint_pre=0,
        sfx_looping="0",
        screenshake=0,
        frames_shake="",
        frames_realization="",
        frames_sfx="",
        additive=0,
        effect="",
        targets=None,
        third_charid=-1,
        third_folder="",
        third_emote=0,
        third_offset="",
        third_flip=0,
        video="",
        relay_seethrough=False,
        exclude_seethrough_area=None,
    ):
        """
        Send an IC message from a client to all applicable clients in the area.
        :param client: speaker
        :param *args: arguments
        """
        if client in self.afkers:
            client.server.client_manager.toggle_afk(client)
        if client and msg.startswith("**") and len(self.testimony) > 0:
            idx = self.testimony_index
            if idx == -1:
                idx = 0
            try:
                lst = list(self.testimony[idx])
                lst[4] = "}}}" + msg[2:]
                self.testimony[idx] = tuple(lst)
                self.broadcast_ooc(f"{client.showname} has amended Statement {idx+1}.")
                if not self.recording:
                    self.testimony_send(idx)
            except IndexError:
                client.send_ooc(f"Something went wrong, couldn't amend Statement {idx+1}!")
            return

        adding = msg.strip() != "" and self.recording and client is not None
        if client and msg.startswith("++") and len(self.testimony) > 0:
            if len(self.testimony) >= 30:
                client.send_ooc("Maximum testimony statement amount reached! (30)")
                return
            adding = True
        elif client:
            # Shout used
            shout = str(button).split("<and>")[0]
            if shout in ["1", "2", "3"]:
                lwr = msg.lower()
                target = ""
                # message contains an "at" sign aka we're referring to someone specific
                if "@" in lwr:
                    target = lwr[lwr.find("@") + 1 :]
                try:
                    opponent = None
                    target = target.lower()
                    if target != "":
                        for t in self.clients:
                            # Ignore ourselves
                            if t == client:
                                continue
                            # We're @num so we're trying to grab a Client ID, don't do shownames
                            if target.strip().isnumeric():
                                if t.id == int(target):
                                    opponent = t
                                    break
                            # Loop through the charnames if it's @text
                            if target in t.char_name.lower() or target.split()[0] in t.char_name.lower():
                                opponent = t
                            # Loop through the shownames next, shownames take priority over charnames
                            if target in t.showname.lower() or target.split()[0] in t.showname.lower():
                                opponent = t

                    old_minigame = self.minigame

                    # Minigame with an opponent
                    if opponent is not None and shout in ["2", "3"]:
                        self.start_debate(client, opponent, shout == "3")
                    # Concede
                    elif shout == "1" and self.minigame != "":
                        commands.ooc_cmd_concede(client, "")
                    # Shouter provided target but no opponent was found
                    elif target != "" or self.minigame in ["Cross Swords", "Scrum Debate"]:
                        raise AreaError("Interjection minigame - target not found!")

                    # Minigame didn't swap as a result of this shout, don't display the shout
                    if self.minigame != "" and self.minigame == old_minigame:
                        button = 0
                except Exception as ex:
                    client.send_ooc(ex)
                    return

            # Minigames
            opposing_team = None
            # If we're on red team
            if client.char_id in client.area.red_team:
                # Set our color to red
                color = 2
                # Offset us to the left
                offset_pair = -25
                # Offset them to the right
                other_offset = 25
                # Our opposing team is blue
                opposing_team = client.area.blue_team
                # Set our pos to "debate"
                pos = "debate"
                if client.area.minigame == "Cross Swords":
                    pos = "cs"
                elif client.area.minigame == "Scrum Debate":
                    pos = "sd"
                elif client.area.minigame == "Panic Talk Action":
                    pos = "pta"
            # If we're on blue team
            elif client.char_id in client.area.blue_team:
                # Set our color to blue
                color = 4
                # Offset them to the right
                offset_pair = 25
                # Offset them to the left
                other_offset = -25
                # Our opposing team is red
                opposing_team = client.area.red_team
                # Set our pos to "debate"
                pos = "debate"
                if client.area.minigame == "Cross Swords":
                    pos = "cs"
                elif client.area.minigame == "Scrum Debate":
                    pos = "sd"
                elif client.area.minigame == "Panic Talk Action":
                    pos = "pta"

            # We're in a minigame w/ team setups
            if opposing_team is not None:
                charid_pair = -1
                third_charid = -1
                # Last speaker is us and our message already paired us with someone, and that someone is on the opposing team
                if (
                    client.area.last_ic_message is not None
                    and client.area.last_ic_message[8] == client.char_id
                    and client.area.last_ic_message[16] != -1
                    and int(client.area.last_ic_message[16].split("^")[0]) in opposing_team
                ):
                    # Set the pair to the person who it was last msg
                    charid_pair = int(client.area.last_ic_message[16].split("^")[0])
                # The person we were trying to find is no longer on the opposing team
                else:
                    # Search through the opposing team's characters
                    for other_cid in opposing_team:
                        charid_pair = other_cid
                        # If last message's charid matches a member of this team, prioritize theirs
                        if client.area.last_ic_message is not None and other_cid == client.area.last_ic_message[8]:
                            break
                # If our pair opponent is found
                if charid_pair != -1:
                    # Search through clients in area
                    for target in client.area.clients:
                        # If we find our target char ID
                        if target.char_id == charid_pair:
                            # Set emote, flip and folder properly
                            other_emote = target.last_sprite
                            other_flip = target.flip
                            other_folder = target.claimed_folder
                            break
                    # Speaker always goes in front
                    charid_pair = f"{charid_pair}^0"

            # medieval mode - Ye Olde English
            if client.medieval or self.medieval_mode:
                msg = client.medieval_message(msg)

            # rainbow text!?!?!?
            if client.rainbow:
                msg = client.rainbow_message(msg)
                color = 4

            if (
                msg.strip() != ""
                or self.last_ic_message is None
                or pos != self.last_ic_message[8]
                or self.last_ic_message[4].strip() != ""
            ):
                database.log_area("chat.ic", client, client.area, message=msg)

        if targets is None:
            targets = set(self.clients)
            # add all targets of the broadcasted areas as well
            for area in self.broadcast_list:
                targets.update(area.clients)
        if relay_seethrough:
            # Clients in areas with a see-through link to this area watch its
            # passing (presence) messages without being in it. The area on the
            # other side of the move is skipped: its users just saw the mover
            # leave/arrive, so the relayed message is redundant for them.
            if not isinstance(targets, set):
                targets = set(targets)
            for area in self.area_manager.areas:
                if area is exclude_seethrough_area:
                    continue
                link = area.links.get(str(self.id))
                if link is not None and link.get("seethrough", False):
                    targets.update(area.clients)
        for c in targets:
            # Blinded clients don't receive IC messages
            if c.blinded:
                continue
            # pos doesn't match listen_pos, we're not listening so make this an OOC message instead
            if c.area == self and c.listen_pos is not None:
                if type(c.listen_pos) is list and not (pos in c.listen_pos) or c.listen_pos == "self" and pos != c.pos:
                    name = ""
                    if cid != -1:
                        name = self.area_manager.char_list[cid]
                    if showname != "":
                        name = showname
                    # Send the mesage as OOC.
                    # Woulda been nice if there was a packet to send messages to IC log
                    # without displaying it in the viewport.
                    c.send_command("CT", f"[pos '{pos}'] {name}", msg)
                    continue

            # Before we send the message, if our remote_listen is different...
            if c.remote_listen in [1, 3]:
                # Make sure to reset the BG back to normal since remote_listen IC/ALL clients might be off sync
                c.send_command("BN", c.area.background, "", c.area.overlay, 0)
            msg_to_send = msg
            if c.area != self:
                msg_to_send = "}}}[" + str(self.id) + "] {{{" + msg
            c.send_command(
                "MS",
                msg_type,
                pre,
                folder,
                # if we're in first person mode, treat our msgs as narration
                "" if c == client and client.firstperson else anim,
                msg_to_send,
                pos,
                sfx,
                emote_mod,
                cid,
                sfx_delay,
                button,
                evidence,
                flip,
                ding,
                color,
                showname,
                charid_pair,
                other_folder,
                other_emote,
                offset_pair,
                other_offset,
                other_flip,
                nonint_pre,
                sfx_looping,
                screenshake,
                frames_shake,
                frames_realization,
                frames_sfx,
                additive,
                effect,
                third_charid,
                third_folder,
                third_emote,
                third_offset,
                third_flip,
                video,
            )
        if self.recording:
            # See if the testimony is supposed to end here.
            scrunched = "".join(e for e in msg if e.isalnum())
            if len(scrunched) > 0 and scrunched.lower() == "end":
                self.recording = False
                self.broadcast_ooc(f"[{client.id}] {client.showname} has ended the testimony.")
                self.send_command("RT", "testimony1", 1)
                return
        if anim == "" or pos == "":
            if self.last_ic_message is not None:
                # Set the pos to last message's pos
                pos = self.last_ic_message[5]
            else:
                # Set the pos to the 0th pos-lock
                if len(self.pos_lock) > 0:
                    pos = self.pos_lock[0]
        args = (
            msg_type,  # 0
            pre,  # 1
            folder,  # 2
            anim,  # 3
            msg,  # 4
            pos,  # 5
            sfx,  # 6
            emote_mod,  # 7
            cid,  # 8
            sfx_delay,  # 9
            button,  # 10
            evidence,  # 11
            flip,  # 12
            ding,  # 13
            color,  # 14
            showname,  # 15
            charid_pair,  # 16
            other_folder,  # 17
            other_emote,  # 18
            offset_pair,  # 19
            other_offset,  # 20
            other_flip,  # 21
            nonint_pre,  # 22
            sfx_looping,  # 23
            screenshake,  # 24
            frames_shake,  # 25
            frames_realization,  # 26
            frames_sfx,  # 27
            additive,  # 28
            effect,  # 29
            third_charid,  # 30
            third_folder,  # 31
            third_emote,  # 32
            third_offset,  # 33
            third_flip,  # 34
            video,  # 35
        )
        self.last_ic_message = args

        if (
            "doorman_webhook" in self.server.config
            and self.server.config["doorman_webhook"]["enabled"]
            and self.area_manager.id == int(self.server.config["doorman_webhook"]["hub_id"])
            and self.id == int(self.server.config["doorman_webhook"]["area_id"])
        ):

            living_clients = len(self.clients)
            afkers = len(self.afkers)
            doorman_needed = living_clients <= 1 or afkers >= living_clients - 1
            if doorman_needed and self.can_call_doorman() and client != None and client.area != None:
                description = f"[{client.id}] {client.name} ({client.showname}) in hub [{client.area.area_manager.id}] {client.area.area_manager.name} [{client.area.id}] {client.area.name}"
                description += f"\n{msg}"
                asyncio.get_running_loop().call_soon(self.server.webhooks.doormancall, description)
                self.set_doorman_call_delay()

        if adding:
            if len(self.testimony) >= 30:
                client.send_ooc("Maximum testimony statement amount reached! (30)")
                return
            if msg.startswith("++"):
                msg = msg[2:]
            # Remove speed modifying chars and start the statement instantly
            msg = "}}}" + msg.replace("{", "").replace("}", "")
            # Non-int pre automatically enabled
            nonint_pre = 1
            # Set emote_mod to conform to nonint_pre
            if emote_mod == 1 or emote_mod == 2:
                emote_mod = 0
            elif emote_mod == 6:
                emote_mod = 5
            # Make it green
            color = 1
            idx = self.testimony_index

            args = (
                msg_type,  # 0
                pre,  # 1
                folder,  # 2
                anim,  # 3
                msg,  # 4
                pos,  # 5
                sfx,  # 6
                emote_mod,  # 7
                cid,  # 8
                sfx_delay,  # 9
                button,  # 10
                evidence,  # 11
                flip,  # 12
                ding,  # 13
                color,  # 14
                showname,  # 15
                charid_pair,  # 16
                other_folder,  # 17
                other_emote,  # 18
                offset_pair,  # 19
                other_offset,  # 20
                other_flip,  # 21
                nonint_pre,  # 22
                sfx_looping,  # 23
                screenshake,  # 24
                frames_shake,  # 25
                frames_realization,  # 26
                frames_sfx,  # 27
                additive,  # 28
                effect,  # 29
                third_charid,  # 30
                third_folder,  # 31
                third_emote,  # 32
                third_offset,  # 33
                third_flip,  # 34
                video,  # 35
            )
            if idx == -1:
                # Add one statement at the very end.
                self.testimony.append(args)
                idx = self.testimony.index(args)
            else:
                # Add one statement ahead of the one we're currently on.
                idx += 1
                self.testimony.insert(idx, args)
            self.broadcast_ooc(f"Statement {idx+1} added.")
            if not self.recording:
                self.testimony_send(idx)

    def set_doorman_call_delay(self):
        """Begin the doorman cooldown."""
        try:
            self.doorman_call_time = round(
                time.time() * 1000.0 + int(self.server.config["doorman_webhook"]["delay"]) * 1000.0
            )
        except:
            self.doorman_call_time = round(time.time() * 1000 + 60000)

    def can_call_doorman(self):
        """Whether or not the area can currently call for a doorman."""
        return (time.time() * 1000.0 - self.doorman_call_time) > 0

    def testimony_send(self, idx):
        """Send the testimony statement at index"""
        try:
            statement = self.testimony[idx]
            self.testimony_index = idx
            targets = self.clients
            for c in targets:
                # Blinded clients don't receive IC messages
                if c.blinded:
                    continue
                # Ignore those losers with listenpos for testimony
                c.send_command("MS", *statement)
        except (ValueError, IndexError):
            raise AreaError("Invalid testimony reference!")

    def broadcast_area_desc(self):
        # DRO Client exclusive
        targets = self.clients
        for c in targets:
            self.broadcast_area_desc_to_target(c)

    def broadcast_area_desc_to_target(self, target):
        reason = ReportCardReason.Nothing
        area_desc = "Nothing particularly interesting."
        # If area description is set
        if self.desc.strip() != "":
            area_desc = self.desc
        # Modifiers
        if target.blinded:
            reason = ReportCardReason.Blinded
            area_desc = "You can't see anything as you are currently blinded."
        elif self.dark:
            reason = ReportCardReason.Blackout
            area_desc = "The lights are off, so you cannot see anything."
        elif not self.can_getarea:
            reason = ReportCardReason.NoPlayerList
        target.send_command("LIST_REASON", reason, area_desc)

    def broadcast_player_list(self):
        """
        Send the player list packet to everyone in the area.
        """
        for target in self.clients:
            self.broadcast_player_list_to_target(target)

    def broadcast_player_list_to_target(self, target):
        return_data = {}
        return_data["packet"] = "player_list"
        special_allowed = target.is_mod or target in self.owners
        player_data_to_send = list()
        player_stuff = list()
        if (self.can_getarea and not self.dark) or special_allowed:
            for c in self.clients:
                if c == target:
                    continue
                if isinstance(c, RemoteClient):
                    continue
                if c.hidden and not special_allowed:
                    continue
                if c.char_id is None:
                    continue
                chara_client_info = {}
                player_stuff.append(str(c.id))
                chara_client_info["id"] = str(c.id)
                chara_client_info["afk"] = str(c in self.afkers)

                # Append the Showname
                # 1.5
                player_stuff.append(str(c.showname))
                chara_client_info["showname"] = str(c.showname)

                # 1.5.1

                # Append the Character Name
                # 1.5
                # if(c.icon_visible):
                char_folder = "Spectator"
                if c.char_id is not None and self.area_manager.is_valid_char_id(c.char_id):
                    char_folder = self.area_manager.char_list[c.char_id]
                player_stuff.append(str(char_folder))
                chara_client_info["character"] = str(char_folder)
                # else:
                #     player_stuff.append("")
                #     chara_client_info["character"] = "NO_CHARA"

                if target.is_mod:
                    # chara_client_info["HDID"] = str(c.hdid)
                    chara_client_info["IPID"] = str(c.ipid)

                # if(c.files):
                #     chara_client_info["url"] = c.files[1]

                # if(c.char_outfit):
                #     chara_client_info["outfit"] = c.char_outfit

                if c.desc:
                    chara_client_info["status"] = c.desc
                player_data_to_send.append(chara_client_info)
        return_data["data"] = player_data_to_send

        json_data = json.dumps(return_data)
        target.send_command("JSN", json_data)
        target.send_command("LP", player_stuff)

    def parse_msg_delay(self, msg):
        """Just returns the delay value between messages.
        :param msg: the string
        :return: delay integer in ms
        """
        return self.msg_delay

    def is_iniswap(self, client, preanim, anim, char, sfx):
        """
        Determine if a client is performing an INI swap.
        :param client: client attempting the INI swap.
        :param preanim: name of preanimation
        :param anim: name of idle/talking animation
        :param char: name of character

        """
        if char.lower() != client.char_name.lower():
            client.iniswap = char
        else:
            client.iniswap = ""

        if self.iniswap_allowed:
            return False
        # Our client is narrating or blankposting via slash command
        if client.narrator or client.blankpost:
            return False
        # Our client is narrating or blankposting via ini editing
        if anim == "" or derelative(anim) == "misc/blank":
            return False
        if char.lower() != client.char_name.lower():
            for char_link in self.server.allowed_iniswaps:
                # Only allow if both the original character and the
                # target character are in the allowed INI swap list
                if client.char_name in char_link and char in char_link:
                    return False
            return True
        return not self.server.char_emotes[char].validate(preanim, anim, sfx)

    def clear_music(self):
        self.music_list.clear()
        self.music_ref = ""

    def load_music(self, path):
        try:
            with open(path, "r", encoding="utf-8") as stream:
                music_list = yaml.safe_load(stream)

            prepath = ""
            for item in music_list:
                # deprecated, use 'replace_music' area pref instead
                # if 'replace' in item:
                #     self.replace_music = item['replace'] is True
                if "use_unique_folder" in item and item["use_unique_folder"] is True:
                    prepath = os.path.splitext(os.path.basename(path))[0] + "/"

                if "category" not in item:
                    continue

                if "songs" in item:
                    for song in item["songs"]:
                        song["name"] = prepath + song["name"]
            self.music_list = music_list
        except ValueError:
            raise
        except AreaError:
            raise

    def add_jukebox_vote(self, client, music_name, length=-1, showname=""):
        """
        Cast a vote on the jukebox.
        :param music_name: track name
        :param length: length of track (Default value = -1)
        :param showname: showname of voter (?) (Default value = '')
        """
        if not self.jukebox:
            return
        if client.change_music_cd():
            client.send_ooc(
                f"You changed the song too many times. Please try again after {int(client.change_music_cd())} seconds."
            )
            return
        if length == 0:
            self.remove_jukebox_vote(client, False)
            if len(self.jukebox_votes) <= 1 or (not self.music_looper or self.music_looper.cancelled()):
                self.start_jukebox()
        else:
            self.remove_jukebox_vote(client, True)
            self.jukebox_votes.append(self.JukeboxVote(client, music_name, length, showname))
            client.send_ooc("Your song was added to the jukebox.")
            if len(self.jukebox_votes) == 1 or (not self.music_looper or self.music_looper.cancelled()):
                self.start_jukebox()

    def remove_jukebox_vote(self, client, silent):
        """
        Removes a vote on the jukebox.
        :param client: client whose vote should be removed
        :param silent: do not notify client

        """
        if not self.jukebox:
            return
        for current_vote in self.jukebox_votes:
            if current_vote.client.id == client.id:
                self.jukebox_votes.remove(current_vote)
        if not silent:
            client.send_ooc("You removed your song from the jukebox.")

    def get_jukebox_picked(self):
        """Randomly choose a track from the jukebox."""
        if not self.jukebox:
            return
        if len(self.jukebox_votes) == 0:
            # Server music list
            song_list = self.server.music_list

            # Hub music list
            if self.area_manager.music_ref != "" and len(self.area_manager.music_list) > 0:
                if self.area_manager.replace_music:
                    song_list = self.area_manager.music_list
                else:
                    song_list = song_list + self.area_manager.music_list

            # Area music list
            if self.music_ref != "" and self.music_ref != self.area_manager.music_ref and len(self.music_list) > 0:
                if self.replace_music:
                    song_list = self.music_list
                else:
                    song_list = song_list + self.music_list

            songs = []
            for c in song_list:
                if "category" in c:
                    # Either play a completely random category, or play a category the last song was in
                    if "songs" in c:
                        if self.music == "" or self.music in [b["name"] for b in c["songs"]]:
                            for s in c["songs"]:
                                looping = "length" not in s or s["length"] == -1
                                if not looping or s["name"] == self.music:
                                    continue
                                songs = songs + [s]
            song = random.choice(songs)
            return self.JukeboxVote(None, song["name"], song["length"], "Jukebox")
        elif len(self.jukebox_votes) == 1:
            song = self.jukebox_votes[0]
            self.remove_jukebox_vote(song.client, True)
            return song
        else:
            weighted_votes = []
            for current_vote in self.jukebox_votes:
                i = 0
                while i < current_vote.chance:
                    weighted_votes.append(current_vote)
                    i += 1
            song = random.choice(weighted_votes)
            self.remove_jukebox_vote(song.client, True)
            return song

    def start_jukebox(self):
        """Initialize jukebox mode if needed and play the next track."""
        if self.music_looper:
            self.music_looper.cancel()

        # There is a probability that the jukebox feature has been turned off since then,
        # we should check that.
        # We also do a check if we were the last to play a song, just in case.
        if not self.jukebox:
            if self.music_player == "The Jukebox" and self.music_player_ipid == "has no IPID":
                self.music = ""
            return

        vote_picked = self.get_jukebox_picked()

        if vote_picked is None:
            self.music = ""
            self.send_command("MC", self.music, -1, "", 1, 0, int(MusicEffect.FADE_OUT))
            return

        if vote_picked.name == self.music:
            return

        if vote_picked.client is not None:
            self.jukebox_prev_char_id = vote_picked.client.char_id
            if vote_picked.showname == "":
                self.send_command(
                    "MC",
                    vote_picked.name,
                    vote_picked.client.char_id,
                    "",
                    1,
                    0,
                    int(MusicEffect.FADE_OUT),
                )
            else:
                self.send_command(
                    "MC",
                    vote_picked.name,
                    vote_picked.client.char_id,
                    vote_picked.showname,
                    1,
                    0,
                    int(MusicEffect.FADE_OUT),
                )
        else:
            self.jukebox_prev_char_id = -1
            self.send_command(
                "MC",
                vote_picked.name,
                0,
                "The Jukebox",
                1,
                0,
                int(MusicEffect.FADE_OUT),
            )

        self.music_player = "The Jukebox"
        self.music_player_ipid = "has no IPID"
        self.music = vote_picked.name

        for current_vote in self.jukebox_votes:
            # Choosing the same song will get your votes down to 0, too.
            # Don't want the same song twice in a row!
            if current_vote.name == vote_picked.name:
                current_vote.chance = 0
            else:
                current_vote.chance += 1

        length = vote_picked.length - 3  # Remove a few seconds to have a smooth fade out
        if length <= 0:  # Length not defined
            length = 120.0  # Play each song for at least 2 minutes

        self.music_looper = asyncio.get_running_loop().call_later(max(5, length), lambda: self.start_jukebox())

    def set_ambience(self, name):
        self.ambience = name
        for client in self.clients:
            self.play_client_ambience(client)

    def play_music(self, name, cid, loop=0, showname="", effects=0):
        """
        Play a track.
        :param name: track name
        :param cid: origin character ID
        :param loop: 1 for clientside looping, 0 for no looping (2.8)
        :param showname: showname of origin user
        :param effects: fade out/fade in/sync/etc. effect bitflags
        """
        # If it's anything other than 0, it's looping. (Legacy music.yaml support)
        if loop != 0:
            loop = 1
        self.music_looping = loop
        self.music_effects = effects
        self.send_command("MC", name, cid, showname, loop, 0, effects)

    def can_send_message(self, client):
        """
        Check if a client can send an IC message in this area.
        :param client: sender
        """
        return (time.time() * 1000.0 - self.next_message_time) > 0

    def cannot_ic_interact(self, client, button="0"):
        """
        Check if this area is muted to a client.
        :param client: sender
        """
        return (
            self.muted
            and not client.is_mod
            and client not in self.owners
            and client.id not in self.invite_list
            # specific use case for joining in a Scrum Debate
            and (self.minigame not in ["Cross Swords", "Scrum Debate"] or button != "2")
        )

    def change_hp(self, side, val):
        """
        Set the penalty bars.
        :param side: 1 for defense; 2 for prosecution
        :param val: value from 0 to 10
        """
        if not 0 <= val <= 10:
            raise AreaError("Invalid penalty value.")
        if not 1 <= side <= 2:
            raise AreaError("Invalid penalty side.")
        if side == 1:
            self.hp_def = val
        elif side == 2:
            self.hp_pro = val
        self.send_command("HP", side, val)

    def change_background_suffix(self, bg_suffix, mode=1):
        self.background_suffix = bg_suffix
        for client in self.clients:
            client.send_command("BN", self.background, client.pos, self.overlay, mode)
        bridge = getattr(self.server, "gm_panel_bridge", None)
        if bridge is not None:
            bridge.on_area_background_changed(self)

    def change_background(self, bg, overlay="", mode=1):
        """
        Set the background and/or overlay.

        parameters:
        bg:      background name
        silent:  should send the pre 2.8 packet or the new one?
        overlay: overlay name (optional)

        :raises: AreaError if `bg` is not in background list

        BN packet implementation:

        Before 2.8 (Changes after sending a IC message):
        BN # <background name>

        AO 2.8 (Clear viewport and update/change background position):
        BN # <background name> # <pos>

        AOG 1.0 (Put a additional image on top of the character):
        BN # <background name> # <pos> # <overlay:str> # <mode:int>

        mode: 0 = pre 2.8 version (change background after IC message)
              1 = 2.8 version (Change background immediately, clearing the viewport)
              2 = Change background without clearing the viewport
              3 = Change the overlay immediately and the background in the next IC message

        The client should be expected to implement at least the first two.


        """
        if self.use_backgrounds_yaml:
            if len(self.server.backgrounds) <= 0:
                raise AreaError(
                    'backgrounds.yaml failed to initialize! Please set "use_backgrounds_yaml" to "false" in the config/config.yaml, or create a new "backgrounds.yaml" list in the "config/" folder.'
                )
            if bg.lower() not in (name.lower() for name in self.server.backgrounds):
                raise AreaError(
                    f'Invalid background name {bg}.\nPlease add it to the "backgrounds.yaml" or change the background name for area [{self.id}] {self.name}.'
                )
        # TODO: Make overlay use  "self.use_overlay_yaml". For now it guessses that it is always disabled.

        if self.dark:
            self.background_dark = bg
        else:
            self._background = bg

        if len(self.pos_lock) > 0:
            for client in self.clients:
                # Update all clients to the pos lock
                if client.pos not in self.pos_lock:
                    client.change_position(self.pos_lock[0])

        self.overlay = overlay

        for client in self.clients:
            client.send_command("BN", client.area.background, client.pos, self.overlay, mode)

        bridge = getattr(self.server, "gm_panel_bridge", None)
        if bridge is not None:
            bridge.on_area_background_changed(self)

    def change_status(self, value):
        """
        Set the status of the area.
        :param value: status code
        """
        value = censor(
            value,
            self.server.censors["whole"],
            self.server.censors["replace"],
            True,
        )
        value = censor(
            value,
            self.server.censors["partial"],
            self.server.censors["replace"],
            False,
        )
        if value.lower() == "hub":
            raise AreaError("Hub Status is a restricted value.")
        if value.lower() == "lfp":
            value = "looking-for-players"
        self.status = value.upper()
        self.area_manager.send_arup_status()

    def change_doc(self, doc="No document."):
        """
        Set the doc link.
        :param doc: doc link (Default value = 'No document.')
        """
        self.doc = doc

    def add_to_judgelog(self, client, msg):
        """
        Append an event to the judge log (max 10 items).
        :param client: event origin
        :param msg: event message
        """
        if len(self.judgelog) >= 10:
            self.judgelog = self.judgelog[1:]
        self.judgelog.append(f"{client.char_name} ({client.ip}) {msg}.")

    def add_music_playing(self, client, name, showname="", autoplay=None):
        """
        Set info about the current track playing.
        :param client: player
        :param showname: showname of player (can be blank)
        :param name: track name
        :param autoplay: if track will play itself as soon as user joins area
        """
        if showname != "":
            self.music_player = f"{showname} ({client.char_name})"
        else:
            self.music_player = client.char_name
        self.music_player_ipid = client.ipid
        self.music = name
        if autoplay is None:
            autoplay = self.music_autoplay
        self.music_autoplay = autoplay

    def get_evidence_list(self, client):
        """
        Get the evidence list of the area.
        :param client: requester
        """
        client.evi_list, evi_list = self.evi_list.create_evi_list(client)
        # insert another dummy numby to account for the silly inventory/evidence swapper
        client.evi_list.insert(0, 0)
        return evi_list

    def broadcast_evidence_list(self):
        """
        Broadcast an updated evidence list.
        LE#<name>&<desc>&<img>#<name>
        """
        for client in self.clients:
            client.update_evidence_list()

    def real_cms(self):
        """
        CMs that are real players, excluding system executors (RemoteClient).
        The script executor may hold CM permission for command checks but must
        not drive CM lifecycle events like area resets or CM listings.
        """
        return {o for o in self._owners if not isinstance(o, RemoteClient)}

    def get_owners(self):
        """
        Get a string of area's owners (CMs).
        :return: message
        """
        msg = ""
        for i in self.real_cms():
            msg += f"[{str(i.id)}] {i.showname}, "
        if len(msg) > 2:
            msg = msg[:-2]
        return msg

    def add_owner(self, client):
        """
        Add a CM to the area.
        """
        self._owners.add(client)

        # Make sure the client's available areas are updated
        self.broadcast_area_list(client)
        # Update CM information on ARUP
        self.area_manager.send_arup_cms()
        # Update the evidence list
        self.broadcast_evidence_list()
        # Update their judge buttons
        self.update_judge_buttons(client)

        self.broadcast_ooc(f"{client.showname} [{client.id}] is CM in this area now.")

        bridge = getattr(self.server, "gm_panel_bridge", None)
        if bridge is not None:
            bridge.on_area_cm_roster_changed(self)

    def remove_owner(self, client, dc=False):
        """
        Remove a CM from the area.
        """
        self._owners.remove(client)
        if not dc and len(client.broadcast_list) > 0:
            client.broadcast_list.clear()
            client.send_ooc("Your broadcast list has been cleared.")

        if self.area_manager.single_cm and len(self.real_cms()) == 0:
            if self.locked:
                self.unlock()
            if self.password != "":
                self.password = ""
            if self.muted:
                self.unmute()
                self.broadcast_ooc("This area is no longer muted.")
            self.name = self.o_name
            self.doc = self.o_doc
            self.desc = self.o_desc
            self.change_background(self.o_background)
            self.pos_lock.clear()

        if not dc:
            # Make sure the client's available areas are updated
            self.broadcast_area_list(client)
            # Update CM information on ARUP
            self.area_manager.send_arup_cms()
            # Update the evidence list
            self.broadcast_evidence_list()
            # Update their judge buttons
            self.update_judge_buttons(client)

        self.broadcast_ooc(f"{client.showname} [{client.id}] is no longer CM in this area.")

        bridge = getattr(self.server, "gm_panel_bridge", None)
        if bridge is not None:
            bridge.on_area_cm_roster_changed(self)

    def broadcast_area_list(self, client=None, refresh=False):
        """
        Send the accessible and visible areas to the client.
        """
        clients = []
        if client is None:
            clients = list(self.clients)
        else:
            clients.append(client)

        update_clients = []
        for c in clients:
            allowed = (c.is_mod or c in self.owners) and not c.available_areas_only
            area_list = c.get_area_list(allowed, allowed)
            if refresh or c.local_area_list != area_list:
                update_clients.append(c)
                c.reload_area_list(area_list)

        # Update ARUP information only for those that need it
        if len(update_clients) > 0:
            self.area_manager.send_arup_status(update_clients)
            self.area_manager.send_arup_lock(update_clients)
            self.area_manager.send_arup_cms(update_clients)

    def time_until_move(self, client):
        """
        Sum up the movement delays. For example,
        if client has 1s move delay, area has 3s move delay, and hub has 2s move delay,
        the resulting delay will be 1+3+2=6 seconds.
        Negative numbers are allowed.
        :return: time left until you can move again or 0.
        """
        secs = round(time.time() * 1000.0 - client.last_move_time)
        total = sum([client.move_delay, self.move_delay, self.area_manager.move_delay])
        test = total * 1000.0 - secs
        if test > 0:
            return test
        return 0

    @property
    def minigame_time_left(self):
        """Time left on the currently running minigame."""
        if not self.minigame_schedule or self.minigame_schedule.cancelled():
            return 0
        return self.minigame_schedule.when() - asyncio.get_running_loop().time()

    def end_minigame(self, reason=""):
        if self.minigame_schedule:
            self.minigame_schedule.cancel()

        self.muted = self.old_muted
        self.invite_list = self.old_invite_list
        self.red_team.clear()
        self.blue_team.clear()
        self.votes_cast.clear()
        self.send_timer_set_time(2, None)
        self.send_ic(
            msg=f"~~}}}}`{self.minigame} END!`\\n{reason}",
            showname="System",
        )
        song = ""
        if "concede" in reason.lower() or "forcibly" in reason.lower():
            if self.minigame == "Scrum Debate":
                song = self.scrum_debate_song_concede
            elif self.minigame == "Cross Swords":
                song = self.cross_swords_song_concede
            elif self.minigame == "Panic Talk Action":
                song = self.panic_talk_action_song_concede
        else:
            if self.minigame == "Scrum Debate":
                song = self.scrum_debate_song_end
            elif self.minigame == "Cross Swords":
                song = self.cross_swords_song_end
            elif self.minigame == "Panic Talk Action":
                song = self.panic_talk_action_song_end
        # Play the song if it's not blank
        if song != "":
            self.music_player = "The Jukebox"
            self.music_player_ipid = "has no IPID"
            self.music = song
            self.send_command(
                "MC",
                song,
                0,
                "The Jukebox",
                1,
                0,
                0,
            )
        self.minigame = ""

    def vote_end_minigame(self, client):
        if client.area.minigame == "":
            client.send_ooc("There is no minigame running right now.")
            return

        valid_voters = [
            c
            for c in self.clients
            if not c.hidden
            and not c in self.afkers
            and not c in self.owners
            and c.char_id not in client.area.blue_team
            and c.char_id not in client.area.red_team
        ]
        if client not in valid_voters:
            client.send_ooc(
                "You're not qualified to vote-end this minigame! (You're a Spectator, Hidden or the area owner)"
            )
            return
        self.votes_cast.add(client)
        votes_casted = len(self.votes_cast)
        votes_needed = round(len(valid_voters) * self.votes_percentage)

        info = f"[{client.id}] {client.showname} is voting to end the minigame!"

        if votes_casted >= votes_needed:
            client.area.end_minigame("Voted to end.")
            info += f"\nSuccessfully voted to end with ({votes_casted}/{votes_needed}) votes."
        else:
            info += f"({votes_casted}/{votes_needed}) votes left."

        self.broadcast_ooc(info)

    def start_debate(self, client, target, pta=False):
        if (client.char_id in self.red_team and target.char_id in self.blue_team) or (
            client.char_id in self.blue_team and target.char_id in self.red_team
        ):
            raise AreaError("Target is already on the opposing team!")

        song = ""
        if self.minigame == "Scrum Debate":
            if pta:
                raise AreaError("You cannot PTA during a Scrum Debate!")
            if target.char_id in self.red_team:
                self.red_team.discard(client.char_id)
                self.blue_team.add(client.char_id)
                self.invite_list.add(client.id)
                team = "🔵blue"
            elif target.char_id in self.blue_team:
                self.blue_team.discard(client.char_id)
                self.red_team.add(client.char_id)
                self.invite_list.add(client.id)
                team = "🔴red"
            else:
                raise AreaError("Target is not part of the minigame!")

            if len(self.blue_team) <= 0:
                self.broadcast_ooc("🔵Blue team conceded!")
                self.end_minigame("√Blue√ team conceded!")
                return
            elif len(self.red_team) <= 0:
                self.broadcast_ooc("🔴Red team conceded!")
                self.end_minigame("~Red~ team conceded!")
                return
            self.broadcast_ooc(f"[{client.id}] {client.showname} is now part of the {team} team!")
            database.log_area(
                "minigame.sd",
                client,
                client.area,
                target=target,
                message=f"{self.minigame} is now part of the {team} team!",
            )
            return
        elif self.minigame == "Cross Swords":
            if target == client:
                self.broadcast_ooc(f"[{client.id}] {client.showname} conceded!")
                self.end_minigame(f"[{client.id}] {client.showname} conceded!")
                return
            if not self.can_scrum_debate:
                raise AreaError("You may not scrum debate in this area!")
            if target.char_id in self.red_team:
                self.red_team.discard(client.char_id)
                self.blue_team.add(client.char_id)
                self.invite_list.add(client.id)
                team = "🔵blue"
            elif target.char_id in self.blue_team:
                self.blue_team.discard(client.char_id)
                self.red_team.add(client.char_id)
                self.invite_list.add(client.id)
                team = "🔴red"
            else:
                raise AreaError("Target is not part of the minigame!")
            timeleft = self.minigame_schedule.when() - asyncio.get_running_loop().time()
            self.minigame_schedule.cancel()
            self.minigame = "Scrum Debate"
            timer = timeleft + self.scrum_debate_added_time
            self.broadcast_ooc(f"[{client.id}] {client.showname} is now part of the {team} team!")
            database.log_area(
                "minigame.sd",
                client,
                client.area,
                target=target,
                message=f"{self.minigame} is now part of the {team} team!",
            )
            song = self.scrum_debate_song_start
        elif self.minigame == "":
            if not pta and not self.can_cross_swords:
                raise AreaError("You may not Cross-Swords in this area!")
            if pta and not self.can_panic_talk_action:
                raise AreaError("You may not PTA in this area!")
            if client == target:
                raise AreaError("You cannot initiate a minigame against yourself!")
            self.old_invite_list = self.invite_list
            self.old_muted = self.muted

            self.muted = True
            self.invite_list.clear()
            self.invite_list.add(client.id)
            self.invite_list.add(target.id)

            self.red_team.clear()
            self.blue_team.clear()
            self.red_team.add(client.char_id)
            self.blue_team.add(target.char_id)

            self.votes_cast.clear()
            if pta:
                self.minigame = "Panic Talk Action"
                timer = self.panic_talk_action_timer
                database.log_area(
                    "minigame.pta",
                    client,
                    client.area,
                    target=target,
                    message=f"{self.minigame} {client.showname} VS {target.showname}",
                )
                song = self.panic_talk_action_song_start
            else:
                self.minigame = "Cross Swords"
                timer = self.cross_swords_timer
                database.log_area(
                    "minigame.cs",
                    client,
                    client.area,
                    target=target,
                    message=f"{self.minigame} {client.showname} VS {target.showname}",
                )
                song = self.cross_swords_song_start
        else:
            if target == client:
                self.broadcast_ooc(f"[{client.id}] {client.showname} conceded!")
                self.end_minigame(f"[{client.id}] {client.showname} conceded!")
                return
            raise AreaError(f"{self.minigame} is happening! You cannot interrupt it.")

        timer = max(5, int(timer))
        # Timer ID 2 is used, start it
        self.send_timer_set_time(2, timer * 1000, True)
        self.minigame_schedule = asyncio.get_running_loop().call_later(
            timer, lambda: self.end_minigame("Timer expired!")
        )

        us = f"🔴[{client.id}] {client.showname} (Red)"
        them = f"🔵[{target.id}] {target.showname} (Blue)"
        for cid in self.blue_team:
            if client.char_id == cid:
                us = f"🔵[{client.id}] {client.showname} (Blue)"
                them = f"🔴[{target.id}] {target.showname} (Red)"
                break
        self.broadcast_ooc(
            f"❗{self.minigame}❗\n{us} objects to {them}!\n⏲You have {timer} seconds.\n/cs <id> to join the debate against target ID."
        )

        # Play the song if it's not blank
        if song != "":
            self.music_player = "The Jukebox"
            self.music_player_ipid = "has no IPID"
            self.music = song
            self.send_command(
                "MC",
                song,
                0,
                "The Jukebox",
                1,
                0,
                0,
            )

    def play_demo(self, client, evidence):
        """
        Start (or chain into) demo playback from an evidence item's description.

        `client` is the requesting client (a player or the system executor); the
        actual playback runs through this area's system executor client, so it
        keeps working even if the requester disconnects or loses permissions.
        """
        instructions = parse_demo_description(evidence.desc)
        if not instructions:
            msg = (
                f"[Demo] Evidence '{evidence.name}' has no demo instructions: "
                "lines must end with '%' and use known packets/commands."
            )
            self.broadcast_ooc(msg)
            return
        self._warn_demo_out_of_range(client, evidence, instructions)
        runner = self.demo_runner
        if runner is None:
            runner = ScriptRunner(self, self.get_script_client())
            self.demo_runner = runner
        runner.start(instructions)

    def stop_demo(self):
        if self.demo_runner is not None:
            self.demo_runner.stop()

    def _warn_demo_out_of_range(self, client, evidence, instructions):
        """
        Warn a human caller about MS packets whose char id is out of range.

        Clients silently drop MS packets whose char id isn't a valid index into
        the server's character list, so a demo captured on a bigger server can
        appear to do nothing here. Chained `/demo` calls (RemoteClient) have no
        human caller and are skipped.
        """
        if client is None or isinstance(client, RemoteClient):
            # No human caller to warn (executor-triggered demos, present/join
            # triggers, chained /demo). Broadcast so GMs in the area see why
            # the demo's IC content won't render.
            target = None
        else:
            target = client
        nchars = len(self.area_manager.char_list)
        for kind, *rest in instructions:
            if kind == "packet" and len(rest) >= 2 and rest[0] == "MS" and len(rest[1]) > 8:
                try:
                    cid = int(rest[1][8])
                except (TypeError, ValueError):
                    continue
                if 0 <= cid < nchars:
                    continue
                # system character is a valid way to handle it.
                if cid == -1:
                    continue
                noun = "character" if nchars == 1 else "characters"
                msg = (
                    f"[Demo] Warning: evidence '{evidence.name}' has an MS packet "
                    f"with char id {cid}, which is out of range (this server only "
                    f"has {nchars} {noun}). The message won't appear on clients."
                )
                if target is None:
                    self.broadcast_ooc(msg)
                else:
                    target.send_ooc(msg)

    class JukeboxVote:
        """Represents a single vote cast for the jukebox."""

        def __init__(self, client, name, length, showname):
            self.client = client
            self.name = name
            self.length = length
            self.chance = 1
            self.showname = showname
