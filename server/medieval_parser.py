"""
Medieval text parser, reimplemented from tf_autorp in the Source 1 SDK 2013
and ported from the Akashi C++ implementation.
"""

import json
import logging
import random
import os

logger = logging.getLogger("medieval")


class MedievalParser:
    """Parses and transforms text into Ye Olde English."""

    def __init__(self, datafile_path="config/text/autorp.json"):
        self.datafile_valid = False
        self.prepended_words = []
        self.appended_words = []
        self.word_replacements = []
        self.word_vector = []

        # For pseudo-random word selection
        self._prev_pre = 0
        self._prev_post = 0

        self._parse_datafile(datafile_path)

    def _parse_datafile(self, datafile_path):
        """Load and parse the autorp.json data file."""
        self.datafile_valid = True

        if not os.path.exists(datafile_path):
            logger.warning(f"Medieval Mode data file not found: {datafile_path}")
            self.datafile_valid = False
            return

        try:
            with open(datafile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Unable to load Medieval Mode data file: {e}")
            self.datafile_valid = False
            return

        # Prepended words
        prepend_obj = data.get("prepended_words", {})
        self.prepended_words = list(prepend_obj.keys())
        if not self.prepended_words:
            self.datafile_valid = False
            return

        # Appended words
        append_obj = data.get("appended_words", {})
        self.appended_words = list(append_obj.keys())
        if not self.appended_words:
            self.datafile_valid = False
            return

        # Word replacements
        replacement_array = data.get("word_replacements", [])
        for rep_obj in replacement_array:
            replacement = {
                "chance": int(rep_obj.get("chance", 0)) if rep_obj.get("chance") else 1,
                "prepend_count": int(rep_obj.get("prepend_count", 0)) if rep_obj.get("prepend_count") else 0,
                "prepended": rep_obj.get("replacement_prepend", []),
                "replacements": rep_obj.get("replacement", []),
                "plural_replacements": rep_obj.get("replacement_plural", []),
                "words": rep_obj.get("word", []),
                "plurals": rep_obj.get("word_plural", []),
                "prev_words": rep_obj.get("prev", []),
            }

            # Add words to the word vector for lookup
            for word in replacement["words"]:
                self.word_vector.append(word.lower())
            for word in replacement["plurals"]:
                self.word_vector.append(word.lower())
            for word in replacement["prev_words"]:
                self.word_vector.append(word.lower())

            self.word_replacements.append(replacement)

        if not self.word_replacements:
            self.datafile_valid = False
            return

        logger.info(f"Medieval Mode loaded {len(self.word_replacements)} word replacements")

    def degrootify(self, message):
        """
        Transform a message into Ye Olde English.
        If the message starts with '-', it won't have pre/post phrases added.
        """
        if not self.datafile_valid:
            return message

        do_pends = True
        final_text = message

        if message.startswith("-"):
            do_pends = False
            final_text = final_text[1:]

        return self._modify_speech(final_text, do_pends, False)

    def _get_random_pre(self):
        """Get a random prepended phrase (25% chance)."""
        if random.randint(1, 4) != 1:
            return ""
        if not self.prepended_words:
            return ""

        self._prev_pre += random.randint(1, 4)
        while self._prev_pre >= len(self.prepended_words):
            self._prev_pre -= len(self.prepended_words)

        return self.prepended_words[self._prev_pre]

    def _get_random_post(self):
        """Get a random appended phrase (20% chance)."""
        if random.randint(1, 5) != 1:
            return ""
        if not self.appended_words:
            return ""

        self._prev_post += random.randint(1, 4)
        while self._prev_post >= len(self.appended_words):
            self._prev_post -= len(self.appended_words)

        return self.appended_words[self._prev_post]

    def _contains_case_insensitive(self, lst, s):
        """Check if a string is in a list (case insensitive)."""
        s_lower = s.lower()
        return any(item.lower() == s_lower for item in lst)

    def _word_matches(self, rep, word, prev_word):
        """
        Check if a word matches a replacement rule.
        Returns: (match_type, used_prev_word)
        match_type: 0 = no match, 1 = singular match, 2 = plural match
        """
        # Check chance
        if rep["chance"] > 1:
            if random.randint(1, rep["chance"]) > 1:
                return (0, False)

        # If it has prev_words, make sure the prev_word matches first
        if rep["prev_words"]:
            if (
                not prev_word
                or not self._contains_case_insensitive(self.word_vector, prev_word)
                or not self._contains_case_insensitive(rep["prev_words"], prev_word)
            ):
                return (0, False)
            used_prev_word = True
        else:
            used_prev_word = False

        # Check match type
        if self._contains_case_insensitive(rep["words"], word):
            return (1, used_prev_word)  # singular match
        elif self._contains_case_insensitive(rep["plurals"], word):
            return (2, used_prev_word)  # plural match
        else:
            return (0, False)

    def _replace_word(self, word, prev_word, symbols=False, word_list_only=False):
        """
        Try to replace a word.
        Returns: (replacement_string, used_prev_word) or (None, False) if no replacement.
        """
        # First, see if we have a replacement from the word list
        for rep in self.word_replacements:
            match_type, used_prev_word = self._word_matches(rep, word, prev_word)
            if match_type == 0:
                continue

            rep_str = ""

            # Add prepended adjectives if any
            if rep["prepended"]:
                used_indices = []
                for count in range(rep["prepend_count"]):
                    # Ensure we don't choose two of the same prepends
                    rnd = random.randint(0, len(rep["prepended"]) - 1)
                    attempts = 0
                    while rnd in used_indices and attempts < 10:
                        rnd = random.randint(0, len(rep["prepended"]) - 1)
                        attempts += 1
                    used_indices.append(rnd)

                    rep_str += rep["prepended"][rnd]
                    if count + 1 < rep["prepend_count"]:
                        rep_str += ", "
                    else:
                        rep_str += " "

            # Add the replacement word
            if match_type == 1:  # singular
                if rep["replacements"]:
                    rnd = random.randint(0, len(rep["replacements"]) - 1)
                    rep_str += rep["replacements"][rnd]
            elif match_type == 2:  # plural
                if rep["plural_replacements"]:
                    rnd = random.randint(0, len(rep["plural_replacements"]) - 1)
                    rep_str += rep["plural_replacements"][rnd]
                elif rep["replacements"]:
                    # Fall back to singular if no plural replacements
                    rnd = random.randint(0, len(rep["replacements"]) - 1)
                    rep_str += rep["replacements"][rnd]

            return (rep_str, used_prev_word)

        # If not symbols mode and not word_list_only, try grammatical modifications
        if not symbols and not word_list_only and len(word) > 0:
            fc = word[0].lower()

            # Randomly replace h's at the front of words with apostrophes
            if fc == "h" and random.randint(1, 2) == 1:
                return ("'" + word[1:], False)

            if len(word) > 3:
                lc = word[-1].lower()
                slc = word[-2].lower()
                lllc = word[-3].lower()

                # Randomly modify words ending in "ed", by replacing the "e" with an apostrophe
                if slc == "e" and lc == "d" and lllc != "e" and random.randint(1, 4) == 1:
                    return (word[:-2] + "'d", False)

                # Randomly append "th" or "st" to any word ending in "ke"
                if slc == "k" and lc == "e" and random.randint(1, 3) == 1:
                    if random.randint(1, 2) == 1:
                        return (word + "th", False)
                    else:
                        return (word + "st", False)

            if len(word) >= 3:
                lc = word[-1].lower()
                slc = word[-2].lower()

                # Randomly append "eth" to words with appropriate last letters
                if random.randint(1, 5) == 1 and lc in ["t", "p", "k", "g", "b", "w"]:
                    return (word + "eth", False)

                # Randomly append "est" to any word ending in "ss"
                if lc == "s" and slc == "s" and random.randint(1, 5) == 1:
                    return (word + "est", False)

            if len(word) > 4:
                lc = word[-1].lower()
                slc = word[-2].lower()
                lllc = word[-3].lower()

                # Randomly prepend "a-" to words ending in "ing", and randomly replace the trailing g with an apostrophe
                if lllc == "i" and slc == "n" and lc == "g":
                    if len(word) > 2 and word[2] != "-":
                        if random.randint(1, 2) == 1:
                            return ("a-" + word, False)
                        else:
                            return ("a-" + word[:-1] + "'", False)

        return (None, False)

    def _perform_replacement(self, rep_str, prev_word, stored_word):
        """
        Perform a/an adjustment based on replacement word.
        Returns the modified stored_word.
        """
        if rep_str:
            fc = rep_str[0].lower()
            # Check if previous word was "an"
            if prev_word.lower() == "an":
                if fc not in ["a", "e", "i", "o", "u"]:
                    # Remove the trailing n
                    stored_word = stored_word[:-1]
            # Check if previous word was "a"
            elif prev_word.lower() == "a":
                if fc in ["a", "e", "i", "o", "u"]:
                    # Add a trailing n
                    stored_word = stored_word + "n"

        return stored_word

    def _modify_speech(self, text, generate_pre_and_post, in_pre_post):
        """Main speech modification function."""
        final_text = ""

        if generate_pre_and_post:
            # See if we generate a pre. If we do, modify it as well.
            pre = self._get_random_pre()
            if pre:
                final_text += self._modify_speech(pre, False, True) + " "

        # Iterate through all words and test them against the replacement list
        prev_word_start = 0
        current_word_start = 0
        cur = 0

        stored_word = ""

        text_len = len(text)

        while cur <= text_len:
            # Check if we've hit a word boundary
            if cur < text_len:
                ch = text[cur]
                if (ch >= "A" and ch <= "Z") or (ch >= "a" and ch <= "z") or ch == "&":
                    cur += 1
                    continue

            # Not alphabetic or &. Hit the end of a word/string.
            current_word_len = cur - current_word_start
            prev_word_len = max(0, current_word_start - prev_word_start - 1)  # -1 for the space

            current_word = text[current_word_start : current_word_start + current_word_len]
            prev_word = text[prev_word_start : prev_word_start + prev_word_len]

            modify_word = True
            skip_one_letter = False

            # pre/post pend blocks only modify words that start with an '&'
            if in_pre_post:
                modify_word = current_word_start < len(text) and text[current_word_start] == "&"
                skip_one_letter = modify_word

            word_to_check = current_word[1:] if skip_one_letter else current_word

            if current_word_len > 0:
                used_prev_word = False

                if modify_word:
                    rep_str, used_prev_word = self._replace_word(word_to_check, prev_word, False, in_pre_post)
                else:
                    rep_str = None

                # If we got an apostrophe-combined word replacement
                if rep_str is not None and modify_word:
                    if stored_word and stored_word[-1:] == "'":
                        combined_word = stored_word + current_word
                        combined_rep, combined_used = self._replace_word(combined_word, "", False, in_pre_post)
                        if combined_rep is not None:
                            rep_str = combined_rep
                            used_prev_word = True

                # Output the previous stored word
                if stored_word:
                    if not used_prev_word:
                        # Perform a/an adjustment
                        adjusted_stored = self._perform_replacement(
                            rep_str if rep_str else current_word, prev_word, stored_word
                        )
                        final_text += adjusted_stored
                        # Append a space, but not if the last character is an apostrophe
                        if stored_word[-1:] != "'":
                            final_text += " "

                # Store the current word (modified or not)
                if rep_str is not None:
                    stored_word = rep_str
                    # Match case of the first letter in the word we're replacing
                    if current_word and stored_word:
                        if current_word[0].isupper():
                            stored_word = stored_word[0].upper() + stored_word[1:]
                        elif current_word[0].islower():
                            stored_word = stored_word[0].lower() + stored_word[1:]
                else:
                    stored_word = word_to_check

            # Finished?
            if cur >= text_len:
                if stored_word:
                    final_text += stored_word
                break

            # If it wasn't a space that ended this word, try checking it for a symbol
            if cur < text_len and text[cur] != " ":
                symbol = text[cur]
                symbol_rep, _ = self._replace_word(symbol, "", True, True)
                if symbol_rep is not None:
                    stored_word += symbol_rep
                else:
                    stored_word += symbol

            # Move on
            cur += 1
            prev_word_start = current_word_start
            current_word_start = cur

        if generate_pre_and_post:
            if final_text:
                last_char = final_text[-1]
                if last_char not in ["?", "!"]:
                    # See if we generate a post. If we do, modify it as well.
                    post = self._get_random_post()
                    if post:
                        if last_char != ".":
                            final_text += ". "
                        else:
                            final_text += " "
                        final_text += self._modify_speech(post, False, True)

        return final_text
