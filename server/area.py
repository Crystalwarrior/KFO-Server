from server import database
from server import commands
from server.evidence import EvidenceList
from server.exceptions import ClientError, AreaError, ArgumentError, ServerError
from server.constants import MusicEffect

from collections import OrderedDict

import asyncio
import random
import time
import arrow

import oyaml as yaml  # ordered yaml
import os
import datetime
import logging

logger = logging.getLogger("area")


class Area:
    class Timer:
        """Represents a single instance of a timer in the area."""

        def __init__(
            self,
            _id,
            Set=False,
            started=False,
            static=None,
            target=None,
            area=None,
            caller=None,
        ):
            self.id = _id
            self.set = Set
            self.started = started
            self.static = static
            self.target = target
            self.area = area
            self.caller = caller
            self.schedule = None
            self.commands = []

        def timer_expired(self):
            if self.schedule:
                self.schedule.cancel()
            # Either the area or the hub was destroyed at some point
            if self.area is None or self is None:
                return

            self.static = datetime.timedelta(0)
            self.started = False

            self.area.broadcast_ooc(f"Timer {self.id+1} has expired.")
            self.call_commands()

        def call_commands(self):
            if self.caller is None:
                return
            if self.area is None or self is None:
                return
            if self.caller not in self.area.owners:
                return
            # We clear out the commands as we call them in order one by one
            while len(self.commands) > 0:
                # Take the first command in the list and run it
                cmd = self.commands.pop(0)
                args = cmd.split(" ")
                cmd = args.pop(0).lower()
                arg = ""
                if len(args) > 0:
                    arg = " ".join(args)[:1024]
                try:
                    old_area = self.caller.area
                    old_hub = self.caller.area.area_manager
                    self.caller.area = self.area
                    commands.call(self.caller, cmd, arg)
                    if old_area and old_area in old_hub.areas:
                        self.caller.area = old_area
                except (ClientError, AreaError, ArgumentError, ServerError) as ex:
                    self.caller.send_ooc(f"[Timer {self.id}] {ex}")
                    # Command execution critically failed somewhere. Clear out all commands so the timer doesn't screw with us.
                    self.commands.clear()
                    # Even tho self.commands.clear() is going to break us out of the while loop, manually return anyway just to be safe.
                    return
                except Exception as ex:
                    self.caller.send_ooc(
                        f"[Timer {self.id}] An internal error occurred: {ex}. Please inform the staff of the server about the issue."
                    )
                    logger.error("Exception while running a command")
                    # Command execution critically failed somewhere. Clear out all commands so the timer doesn't screw with us.
                    self.commands.clear()
                    # Even tho self.commands.clear() is going to break us out of the while loop, manually return anyway just to be safe.
                    return

    """Represents a single instance of an area."""

    def __init__(self, area_manager, name):
        self.clients = set()
        self.invite_list = set()
        self.area_manager = area_manager
        self._name = name

        # Initialize prefs
        self.background = "default"
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
        self.o_background = self.background

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
        self.timers = [self.Timer(x) for x in range(20)]

        # Demo stuff
        self.demo = []
        self.demo_schedule = None

        # Commands to call when certain triggers are fulfilled.
        # #Requires at least 1 area owner to exist to determine permission.
        self.triggers = {
            "join": "",  # User joins the area.
            "leave": "",  # User leaves the area.
        }

    @property
    def name(self):
        """Area's name string. Abbreviation is also updated according to this."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = value.strip()
        while "<num>" in self._name or "<percent>" in self._name:
            self._name = self._name.replace(
                "<num>", "").replace("<percent>", "")
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

    def trigger(self, trig, target):
        """Call the trigger's associated command."""
        if target.hidden:
            return

        if len(self.owners) <= 0:
            return

        arg = self.triggers[trig]
        if arg == "":
            return

        # Sort through all the owners, with GMs coming first and CMs coming second
        sorted_owners = sorted(
            self.owners,
            key=lambda x: 0
            if (x in self.area_manager.owners)
            else 1
            if (x in self._owners)
            else 2,
        )
        # Pick the owner with highest permission - game master, if one exists.
        # This permission system may be out of wack, but it *should* be good for now
        owner = sorted_owners[0]

        arg = (
            arg.replace("<cid>", str(target.id))
            .replace("<showname>", target.showname)
            .replace("<char>", target.char_name)
        )
        args = arg.split(" ")
        cmd = args.pop(0).lower()
        if len(args) > 0:
            arg = " ".join(args)[:1024]
        try:
            old_area = owner.area
            old_hub = owner.area.area_manager
            owner.area = self
            commands.call(owner, cmd, arg)
            if old_area and old_area in old_hub.areas:
                owner.area = old_area
        except (ClientError, AreaError, ArgumentError, ServerError) as ex:
            owner.send_ooc(f"[Area {self.id}] {ex}")
        except Exception as ex:
            owner.send_ooc(
                f"[Area {self.id}] An internal error occurred: {ex}. Please inform the staff of the server about the issue."
            )
            logger.error("Exception while running a command")

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
            self.background = area["background"]
            self.o_background = self.background
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
            self.load_music(f"storage/musiclists/{self.music_ref}.yaml")

        if "client_music" in area:
            self.client_music = area["client_music"]
        if "replace_music" in area:
            self.replace_music = area["replace_music"]
        if "ambience" in area:
            self.ambience = area["ambience"]
        if "can_dj" in area:
            self.can_dj = area["can_dj"]
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
        if 'passing_msg' in area:
            self.passing_msg = area['passing_msg']
        if 'msg_delay' in area:
            self.msg_delay = area['msg_delay']
        if 'present_reveals_evidence' in area:
            self.present_reveals_evidence = area['present_reveals_evidence']

        if "evidence" in area and len(area["evidence"]) > 0:
            self.evi_list.evidences.clear()
            self.evi_list.import_evidence(area["evidence"])
            self.broadcast_evidence_list()

        if "links" in area and len(area["links"]) > 0:
            self.links.clear()
            for key, value in area["links"].items():
                locked, hidden, target_pos, can_peek, evidence, password = (
                    False,
                    False,
                    "",
                    True,
                    [],
                    "",
                )
                if "locked" in value:
                    locked = value["locked"]
                if "hidden" in value:
                    hidden = value["hidden"]
                if "target_pos" in value:
                    target_pos = value["target_pos"]
                if "can_peek" in value:
                    can_peek = value["can_peek"]
                if "evidence" in value:
                    evidence = value["evidence"]
                if "password" in value:
                    password = value["password"]
                self.link(key, locked, hidden, target_pos,
                          can_peek, evidence, password)

        # Update the clients in that area
        if self.dark:
            self.change_background(self.background_dark)
        else:
            self.change_background(self.background)
        self.change_hp(1, self.hp_def)
        self.change_hp(2, self.hp_pro)
        if self.ambience:
            self.set_ambience(self.ambience)
        if self.music_autoplay:
            for client in self.clients:
                if self.music != client.playing_audio[0]:
                    client.send_command(
                        "MC", self.music, -1, "", self.music_looping, 0, self.music_effects
                    )

    def save(self):
        area = OrderedDict()
        area["area"] = self.name
        area["background"] = self.background
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
        if len(self.evi_list.evidences) > 0:
            area["evidence"] = [e.to_dict() for e in self.evi_list.evidences]
        if len(self.links) > 0:
            area["links"] = self.links
        return area

    def new_client(self, client):
        """Add a client to the area."""
        self.clients.add(client)
        if client.char_id is not None:
            database.log_area("area.join", client, self)

        if self.music_autoplay and self.music != client.playing_audio[0]:
            client.send_command(
                "MC", self.music, -1, "", self.music_looping, 0, self.music_effects
            )

        # Update the timers for the client
        self.update_timers(client)

        if self.ambience != client.playing_audio[1]:
            # Play the ambience
            client.send_command(
                "MC",
                self.ambience,
                -1,
                "",
                1,
                1,
                int(MusicEffect.FADE_OUT |
                    MusicEffect.FADE_IN | MusicEffect.SYNC_POS),
            )

        if client.subtheme != self.area_manager.subtheme:
            client.send_command("ST", self.area_manager.subtheme, "1")

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
            s = int(not timer.started)
            current_time = timer.static
            if timer.started:
                current_time = timer.target - arrow.get()
            int_time = int(current_time.total_seconds()) * 1000
            # Unhide the timer
            client.send_command("TI", 0, 2, int_time)
            # Start the timer
            client.send_command("TI", 0, s, int_time)
        elif not running_only:
            # Stop the timer
            client.send_command("TI", 0, 3, 0)
            # Hide the timer
            client.send_command("TI", 0, 1, 0)

        # Area timers
        for timer_id, timer in enumerate(self.timers):
            # Send static time if applicable
            if timer.set:
                s = int(not timer.started)
                current_time = timer.static
                if timer.started:
                    current_time = timer.target - arrow.get()
                int_time = int(current_time.total_seconds()) * 1000
                # Start the timer
                client.send_command("TI", timer_id + 1, s, int_time)
                # Unhide the timer
                client.send_command("TI", timer_id + 1, 2, int_time)
                # client.send_ooc(f"Timer {timer_id+1} is at {current_time}")
            elif not running_only:
                # Stop the timer
                client.send_command("TI", timer_id + 1, 1, 0)
                # Hide the timer
                client.send_command("TI", timer_id + 1, 3, 0)

    def remove_client(self, client):
        """Remove a disconnected client from the area."""
        if client.hidden_in is not None:
            client.hide(False, hidden=True)
        if self.area_manager.single_cm:
            # Remove their owner status due to single_cm pref. remove_owner will unlock the area if they were the last CM.
            if client in self._owners:
                self.remove_owner(client)
                client.send_ooc(
                    "You can only be a CM of a single area in this hub.")
        if self.locking_allowed:
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

        # Update everyone's available characters list
        # Commented out due to potentially causing clientside lag...
        # self.send_command('CharsCheck',
        #                     *client.get_available_char_list())

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

    def link(
        self,
        target,
        locked=False,
        hidden=False,
        target_pos="",
        can_peek=True,
        evidence=[],
        password="",
    ):
        """
        Sets up a one-way connection between this area and targeted area.
        Returns the link dictionary.
        :param target: the targeted Area ID to connect
        :param locked: is the link unusable?
        :param hidden: is the link invisible?
        :param target_pos: which position should we end up in when we come through
        :param can_peek: can you peek through this path?
        :param evidence: a list of evidence from which this link will be accessible when you hide in it
        :param password: the password you need to input to pass through this link

        """
        link = {
            "locked": locked,
            "hidden": hidden,
            "target_pos": target_pos,
            "can_peek": can_peek,
            "evidence": evidence,
            "password": password,
        }
        self.links[str(target)] = link
        return link

    def unlink(self, target):
        try:
            del self.links[str(target)]
        except KeyError:
            raise AreaError(
                f"Link {target} does not exist in Area {self.name}!")

    def is_char_available(self, char_id):
        """
        Check if a character is available for use.
        :param char_id: character ID
        """
        return char_id not in [x.char_id for x in self.clients]

    def get_rand_avail_char_id(self):
        """Get a random available character ID."""
        avail_set = set(range(len(self.area_manager.char_list))) - {
            x.char_id for x in self.clients
        }
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
            if (
                c.remote_listen == 3
                or (cmd == "CT" and c.remote_listen == 2)
                or (cmd == "MS" and c.remote_listen == 1)
            ):
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
                if c.area.background != bg:
                    c.send_command("BN", bg)
                c.send_command(cmd, *args)
                if c.area.background != bg:
                    c.send_command("BN", c.area.background)

    def broadcast_ooc(self, msg):
        """
        Broadcast an OOC message to all clients in the area.
        :param msg: message
        """
        self.send_command("CT", self.server.config["hostname"], msg, "1")
        self.send_owner_command(
            "CT", f"[{self.id}]" + self.server.config["hostname"], msg, "1"
        )

    def send_ic(self,
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
                effect="", targets=None):
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
                self.broadcast_ooc(
                    f"{client.showname} has amended Statement {idx+1}.")
                if not self.recording:
                    self.testimony_send(idx)
            except IndexError:
                client.send_ooc(
                    f"Something went wrong, couldn't amend Statement {idx+1}!"
                )
            return

        adding = msg.strip(
        ) != "" and self.recording and client is not None
        if client and msg.startswith("++") and len(self.testimony) > 0:
            if len(self.testimony) >= 30:
                client.send_ooc(
                    "Maximum testimony statement amount reached! (30)")
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
                    target = lwr[lwr.find("@") + 1:]
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
                        raise AreaError(
                            "Interjection minigame - target not found!")

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
                # Last speaker is us and our message already paired us with someone, and that someone is on the opposing team
                if (
                    client.area.last_ic_message is not None
                    and client.area.last_ic_message[8] == client.char_id
                    and client.area.last_ic_message[16] != -1
                    and int(client.area.last_ic_message[16].split("^")[0])
                    in opposing_team
                ):
                    # Set the pair to the person who it was last msg
                    charid_pair = int(
                        client.area.last_ic_message[16].split("^")[0]
                    )
                # The person we were trying to find is no longer on the opposing team
                else:
                    # Search through the opposing team's characters
                    for other_cid in opposing_team:
                        charid_pair = other_cid
                        # If last message's charid matches a member of this team, prioritize theirs
                        if (
                            client.area.last_ic_message is not None
                            and other_cid == client.area.last_ic_message[8]
                        ):
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
                database.log_area("chat.ic", client,
                                  client.area, message=msg)

        if targets is None:
            targets = self.clients
        for c in targets:
            # Blinded clients don't receive IC messages
            if c.blinded:
                continue
            # pos doesn't match listen_pos, we're not listening so make this an OOC message instead
            if c.listen_pos is not None:
                if (
                    type(c.listen_pos) is list
                    and not (pos in c.listen_pos)
                    or c.listen_pos == "self"
                    and pos != c.pos
                ):
                    name = ""
                    if cid != -1:
                        name = self.area_manager.char_list[cid]
                    if showname != "":
                        name = showname
                    # Send the mesage as OOC.
                    # Woulda been nice if there was a packet to send messages to IC log
                    # without displaying it in the viewport.
                    c.send_command(
                        "CT", f"[pos '{pos}'] {name}", msg)
                    continue
            c.send_command("MS", msg_type,
                           pre,
                           folder,
                           # if we're in first person mode, treat our msgs as narration
                           "" if c == client and client.firstperson else anim,
                           msg,
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
                           effect)
        if self.recording:
            # See if the testimony is supposed to end here.
            scrunched = "".join(e for e in msg if e.isalnum())
            if len(scrunched) > 0 and scrunched.lower() == "end":
                self.recording = False
                self.broadcast_ooc(
                    f"[{client.id}] {client.showname} has ended the testimony."
                )
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
        )
        self.last_ic_message = args

        if adding:
            if len(self.testimony) >= 30:
                client.send_ooc(
                    "Maximum testimony statement amount reached! (30)")
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
            if len(self.jukebox_votes) <= 1 or (
                not self.music_looper or self.music_looper.cancelled()
            ):
                self.start_jukebox()
        else:
            self.remove_jukebox_vote(client, True)
            self.jukebox_votes.append(
                self.JukeboxVote(client, music_name, length, showname)
            )
            client.send_ooc("Your song was added to the jukebox.")
            if len(self.jukebox_votes) == 1 or (
                not self.music_looper or self.music_looper.cancelled()
            ):
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
            if (
                self.area_manager.music_ref != ""
                and len(self.area_manager.music_list) > 0
            ):
                if self.area_manager.replace_music:
                    song_list = self.area_manager.music_list
                else:
                    song_list = song_list + self.area_manager.music_list

            # Area music list
            if (
                self.music_ref != ""
                and self.music_ref != self.area_manager.music_ref
                and len(self.music_list) > 0
            ):
                if self.replace_music:
                    song_list = self.music_list
                else:
                    song_list = song_list + self.music_list

            songs = []
            for c in song_list:
                if "category" in c:
                    # Either play a completely random category, or play a category the last song was in
                    if "songs" in c:
                        if self.music == "" or self.music in [
                            b["name"] for b in c["songs"]
                        ]:
                            for s in c["songs"]:
                                if s["length"] == 0 or s["name"] == self.music:
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
            if (
                self.music_player == "The Jukebox"
                and self.music_player_ipid == "has no IPID"
            ):
                self.music = ""
            return

        vote_picked = self.get_jukebox_picked()

        if vote_picked is None:
            self.music = ""
            self.send_command("MC", self.music, -1, "", 1,
                              0, int(MusicEffect.FADE_OUT))
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

        length = (
            vote_picked.length - 3
        )  # Remove a few seconds to have a smooth fade out
        if length <= 0:  # Length not defined
            length = 120.0  # Play each song for at least 2 minutes

        self.music_looper = asyncio.get_running_loop().call_later(
            max(5, length), lambda: self.start_jukebox()
        )

    def set_ambience(self, name):
        self.ambience = name
        self.send_command(
            "MC",
            self.ambience,
            -1,
            "",
            1,
            1,
            int(MusicEffect.FADE_OUT | MusicEffect.FADE_IN | MusicEffect.SYNC_POS),
        )

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

    def change_background(self, bg, silent=False, overlay="", mode=-1):
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
            self.background = bg

        if len(self.pos_lock) > 0:
            for client in self.clients:
                # Update all clients to the pos lock
                if client.pos not in self.pos_lock:
                    client.change_position(self.pos_lock[0])

        if overlay != "":
            # In case "mode" is unspecified
            if mode == -1:
                if silent:
                    mode = 0
                else:
                    mode = 1
            for client in self.clients:
                client.send_command("BN", bg, client.pos, overlay, mode)

        # Pre AOG packet fallback
        # In case overlay wasn't specified
        elif silent:
            for client in self.clients:
                client.send_command("BN", bg)
        else:
            for client in self.clients:
                client.send_command("BN", bg, client.pos)

    def change_status(self, value):
        """
        Set the status of the area.
        :param value: status code
        """
        allowed_values = (
            "idle",
            "rp",
            "casing",
            "looking-for-players",
            "lfp",
            "recess",
            "gaming",
        )
        if value.lower() not in allowed_values:
            raise AreaError(
                f'Invalid status. Possible values: {", ".join(allowed_values)}'
            )
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
        if client.blinded:
            return [0]
        return evi_list

    def broadcast_evidence_list(self):
        """
        Broadcast an updated evidence list.
        LE#<name>&<desc>&<img>#<name>
        """
        for client in self.clients:
            client.send_command("LE", *self.get_evidence_list(client))

    def get_owners(self):
        """
        Get a string of area's owners (CMs).
        :return: message
        """
        msg = ""
        for i in self._owners:
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

        self.broadcast_ooc(
            f"{client.showname} [{client.id}] is CM in this area now.")

    def remove_owner(self, client, dc=False):
        """
        Remove a CM from the area.
        """
        self._owners.remove(client)
        if not dc and len(client.broadcast_list) > 0:
            client.broadcast_list.clear()
            client.send_ooc("Your broadcast list has been cleared.")

        if self.area_manager.single_cm and len(self._owners) == 0:
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

        self.broadcast_ooc(
            f"{client.showname} [{client.id}] is no longer CM in this area."
        )

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
            allowed = c.is_mod or c in self.owners
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
        total = sum([client.move_delay, self.move_delay,
                    self.area_manager.move_delay])
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
        # Timer ID 2 is used for minigames
        # 3 stands for unset and hide
        self.send_command("TI", 2, 3)
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
            self.broadcast_ooc(
                f"[{client.id}] {client.showname} is now part of the {team} team!"
            )
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
                self.broadcast_ooc(
                    f"[{client.id}] {client.showname} conceded!")
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
            self.broadcast_ooc(
                f"[{client.id}] {client.showname} is now part of the {team} team!"
            )
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
                raise AreaError(
                    "You cannot initiate a minigame against yourself!")
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
                self.broadcast_ooc(
                    f"[{client.id}] {client.showname} conceded!")
                self.end_minigame(f"[{client.id}] {client.showname} conceded!")
                return
            raise AreaError(
                f"{self.minigame} is happening! You cannot interrupt it.")

        timer = max(5, int(timer))
        # Timer ID 2 is used
        self.send_command("TI", 2, 2)
        self.send_command("TI", 2, 0, timer * 1000)
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

    def play_demo(self, client):
        if self.demo_schedule:
            self.demo_schedule.cancel()
        if len(self.demo) <= 0:
            self.stop_demo()
            return
        if not (client in self.owners):
            client.send_ooc(
                f"[Demo] Playback stopped due to you having insufficient permissions! (Not CM/GM anymore)")
            self.stop_demo()
            return

        packet = self.demo.pop(0)
        header = packet[0]
        args = packet[1:]
        # It's a wait packet
        if header == "wait":
            secs = float(args[0]) / 1000
            self.demo_schedule = asyncio.get_running_loop().call_later(
                secs, lambda: self.play_demo(client)
            )
            return
        if header.startswith("/"):  # It's a command call
            # TODO: make this into a global function so commands can be called from anywhere in code...
            cmd = header[1:].lower()
            arg = ""
            if len(args) > 0:
                arg = " ".join(args)[:1024]
            try:
                called_function = f"ooc_cmd_{cmd}"
                if len(client.server.command_aliases) > 0 and not hasattr(
                    commands, called_function
                ):
                    if cmd in client.server.command_aliases:
                        called_function = (
                            f"ooc_cmd_{client.server.command_aliases[cmd]}"
                        )
                if not hasattr(commands, called_function):
                    client.send_ooc(
                        f"[Demo] Invalid command: {cmd}. Use /help to find up-to-date commands."
                    )
                    self.stop_demo()
                    return
                getattr(commands, called_function)(client, arg)
                # Switching to another demo (can't have multiple concurrent demos running)
                if cmd == "demo":
                    return
            except (ClientError, AreaError, ArgumentError, ServerError) as ex:
                client.send_ooc(f"[Demo] {ex}")
                self.stop_demo()
                return
            except Exception as ex:
                client.send_ooc(
                    f"[Demo] An internal error occurred: {ex}. Please inform the staff of the server about the issue."
                )
                logger.error("Exception while running a command")
                self.stop_demo()
                return
        elif len(client.broadcast_list) > 0:
            for area in client.broadcast_list:
                if header == "MS":
                    # If we're on narration pos
                    if args[5] == "":
                        if area.last_ic_message is not None:
                            # Set the pos to last message's pos
                            args[5] = area.last_ic_message[5]
                        else:
                            # Set the pos to the 0th pos-lock
                            if len(self.pos_lock) > 0:
                                args[5] = self.pos_lock[0]
                area.send_command(header, *args)
        else:
            if header == "MS":
                # If we're on narration pos
                if args[5] == "":
                    if self.last_ic_message is not None:
                        # Set the pos to last message's pos
                        args[5] = self.last_ic_message[5]
                    else:
                        # Set the pos to the 0th pos-lock
                        if len(self.pos_lock) > 0:
                            args[5] = self.pos_lock[0]
            self.send_command(header, *args)
        # Proceed to next demo line
        self.play_demo(client)

    def stop_demo(self):
        if self.demo_schedule:
            self.demo_schedule.cancel()
        self.demo.clear()

        # reset the packets the demo could have modified

        # Get defense HP bar
        self.send_command("HP", 1, self.hp_def)
        # Get prosecution HP bar
        self.send_command("HP", 2, self.hp_pro)

        # Send the background information
        if self.dark:
            self.send_command("BN", self.background_dark)
        else:
            self.send_command("BN", self.background)

    class JukeboxVote:
        """Represents a single vote cast for the jukebox."""

        def __init__(self, client, name, length, showname):
            self.client = client
            self.name = name
            self.length = length
            self.chance = 1
            self.showname = showname
