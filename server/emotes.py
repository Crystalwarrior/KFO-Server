from os import path
from configparser import ConfigParser

import logging

logger = logging.getLogger("emotes")

char_dir = "characters"


class Emotes:
    """
    Represents a list of emotes read in from a character INI file
    used for validating which emotes can be sent by clients.
    """

    def __init__(self, name):
        self.name = name
        self.emotes = set()
        self.read_ini()

    def read_ini(self):
        char_ini = ConfigParser(
            comment_prefixes=("=", "-", "#", ";", "//", "\\\\"),
            allow_no_value=True,
            strict=False,
            empty_lines_in_values=False,
        )
        try:
            char_path = path.join(char_dir, self.name, "char.ini")
            with open(char_path, encoding="utf-8-sig") as f:
                char_ini.read_file(f)
                logger.info(
                    "Found char.ini for %s that can be used for iniswap restrictions!",
                    char_path
                )
        except FileNotFoundError:
            return

        # cuz people making char.ini's don't care for no case in sections
        char_ini = dict((k.lower(), v) for k, v in char_ini.items())
        try:
            for emote_id in range(1, int(char_ini["emotions"]["number"]) + 1):
                try:
                    emote_id = str(emote_id)
                    _name, preanim, anim, _mod = char_ini["emotions"][
                        str(emote_id)
                    ].split("#")[:4]
                    # if "soundn" in char_ini and emote_id in char_ini["soundn"]:
                    #     sfx = char_ini["soundn"][str(emote_id)] or ""
                    #     if sfx != "" and len(sfx) == 1:
                    #         # Often, a one-character SFX is a placeholder for no sfx,
                    #         # so allow it
                    #         sfx = ""
                    # else:
                    #     sfx = ""

                    # sfx checking is not performed due to custom sfx being possible, so don't bother for now
                    sfx = ""
                    self.emotes.add(
                        (preanim.lower(), anim.lower(), sfx.lower()))
                except KeyError as e:
                    logger.warning(
                        "Broken key %s in character file %s. "
                        "This indicates a malformed character INI file.", e.args[0], char_path
                    )
        except KeyError as e:
            logger.warning(
                "Unknown key %s in character file %s. "
                "This indicates a malformed character INI file.", e.args[0], char_path
            )
            return
        except ValueError as e:
            logger.warning(
                "Value error in character file %s:\n%ss\n"
                "This indicates a malformed character INI file.", char_path, e
            )
            return

    def validate(self, preanim, anim, sfx):
        """
        Determines whether or not an emote canonically belongs to this
        character (that is, it is defined server-side).
        """
        # There are no emotes loaded, so allow anything
        if len(self.emotes) == 0:
            return True
        # sfx checking is skipped due to custom sound list
        sfx = ""
        # Loop through emotes
        for emote in self.emotes:
            # If we find an emote that matches all 3, allow it
            if (preanim == "" or emote[0] == preanim) and (anim == "" or emote[1] == anim) and (sfx == "" or emote[2] == sfx):
                return True
        return False
