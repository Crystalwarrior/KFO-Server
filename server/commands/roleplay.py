import random

import asyncio
import arrow
import time
import datetime
import pytimeparse
import shlex

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError

from . import mod_only
from .. import commands

__all__ = [
    "ooc_cmd_roll",
    "ooc_cmd_rollp",
    "ooc_cmd_notecard",
    "ooc_cmd_notecard_clear",
    "ooc_cmd_notecard_reveal",
    "ooc_cmd_notecard_check",
    "ooc_cmd_vote",
    "ooc_cmd_vote_clear",
    "ooc_cmd_vote_reveal",
    "ooc_cmd_vote_check",
    "ooc_cmd_rolla_reload",
    "ooc_cmd_rolla_set",
    "ooc_cmd_rolla",
    "ooc_cmd_coinflip",
    "ooc_cmd_8ball",
    "ooc_cmd_rps",
    "ooc_cmd_rps_rules",
    "ooc_cmd_timer",
    "ooc_cmd_demo",
    "ooc_cmd_trigger",
    "ooc_cmd_format_timer",
    "ooc_cmd_timer_interval",
    "ooc_cmd_ooc_actions",
]


def rtd(arg):
    DICE_MAX = 11037
    NUMDICE_MAX = 20
    MODIFIER_LENGTH_MAX = 12  # Change to a higher at your own risk
    ACCEPTABLE_IN_MODIFIER = "1234567890+-*/().r"
    MAXDIVZERO_ATTEMPTS = 10
    MAXACCEPTABLETERM = DICE_MAX * 10  # Change to a higher number at your own risk

    special_calculation = False
    args = arg.split(" ")
    arg_length = len(args)

    if arg != "":
        if arg_length == 2:
            dice_type, modifiers = args
            if len(modifiers) > MODIFIER_LENGTH_MAX:
                raise ArgumentError("The given modifier is too long to compute. Please try a shorter one")
        elif arg_length == 1:
            dice_type, modifiers = arg, ""
        else:
            raise ArgumentError(
                "This command takes one or two arguments. Use /roll [<num of rolls>]d[<max>] [modifiers]"
            )

        dice_type = dice_type.split("d")
        if len(dice_type) == 1:
            dice_type.insert(0, 1)
        if dice_type[0] == "":
            dice_type[0] = "1"

        try:
            num_dice, chosen_max = int(dice_type[0]), int(dice_type[1])
        except ValueError:
            raise ArgumentError("Expected integer value for number of rolls and max value of dice")

        if not 1 <= num_dice <= NUMDICE_MAX:
            raise ArgumentError("Number of rolls must be between 1 and {}".format(NUMDICE_MAX))
        if not 1 <= chosen_max <= DICE_MAX:
            raise ArgumentError("Dice value must be between 1 and {}".format(DICE_MAX))

        for char in modifiers:
            if char not in ACCEPTABLE_IN_MODIFIER:
                raise ArgumentError("Expected numbers and standard mathematical operations in modifier")
            if char == "r":
                special_calculation = True
        if "**" in modifiers:  # Exponentiation manually disabled, it can be pretty dangerous
            raise ArgumentError("Expected numbers and standard mathematical operations in modifier")
    else:
        num_dice, chosen_max, modifiers = 1, 6, ""  # Default

    roll = ""
    Sum = 0

    for i in range(num_dice):
        divzero_attempts = 0
        while True:
            raw_roll = str(random.randint(1, chosen_max))
            if modifiers == "":
                aux_modifier = ""
                mid_roll = int(raw_roll)
            else:
                if special_calculation:
                    aux_modifier = modifiers.replace("r", raw_roll) + "="
                elif modifiers[0].isdigit():
                    aux_modifier = raw_roll + "+" + modifiers + "="
                else:
                    aux_modifier = raw_roll + modifiers + "="

                # Prevent any terms from reaching past MAXACCEPTABLETERM in order to prevent server lag due to potentially frivolous dice rolls
                aux = aux_modifier[:-1]
                for i in "+-*/()":
                    aux = aux.replace(i, "!")
                aux = aux.split("!")
                for i in aux:
                    try:
                        if i != "" and round(float(i)) > MAXACCEPTABLETERM:
                            raise ArgumentError(
                                "Given mathematical formula takes numbers past the server's computation limit"
                            )
                    except ValueError:
                        raise ArgumentError("Given mathematical formula has a syntax error and cannot be computed")

                try:
                    mid_roll = round(eval(aux_modifier[:-1]))  # By this point it should be 'safe' to run eval
                except SyntaxError:
                    raise ArgumentError("Given mathematical formula has a syntax error and cannot be computed")
                except TypeError:  # Deals with inputs like 3(r-1)
                    raise ArgumentError("Given mathematical formula has a syntax error and cannot be computed")
                except ZeroDivisionError:
                    divzero_attempts += 1
                    if divzero_attempts == MAXDIVZERO_ATTEMPTS:
                        raise ArgumentError(
                            "Given mathematical formula produces divisions by zero too often and cannot be computed"
                        )
                    continue
            break

        final_roll = mid_roll  # min(chosen_max,max(1,mid_roll))
        Sum += final_roll
        if final_roll != mid_roll:
            final_roll = "|" + str(
                final_roll
            )  # This visually indicates the roll was capped off due to exceeding the acceptable roll range
        else:
            final_roll = str(final_roll)
        if modifiers != "":
            roll += str(raw_roll + ":")
        roll += str(aux_modifier + final_roll) + ", "
    roll = roll[:-2]
    if num_dice > 1:
        roll = "(" + roll + ")"

    return roll, num_dice, chosen_max, modifiers, Sum


def ooc_cmd_roll(client, arg):
    """
    Roll a die. The result is shown publicly.
    Example: /roll 2d6 +5 would roll two 6-sided die and add 5 to every result.
    Rolls a 1d6 if blank
    X is the number of dice, Y is the maximum value on the die.
    Usage: /rollp [value/XdY] ["+5"/"-5"/"*5"/"/5"]
    """
    roll, num_dice, chosen_max, _modifiers, Sum = rtd(arg)

    client.area.broadcast_ooc(
        f"[👉🎲] [{client.id}] {client.showname} rolled:\n {roll} out of {chosen_max}."
        + (f"\nThe total sum is {Sum}." if num_dice > 1 else "")
    )
    database.log_area("roll", client, client.area, message=f"{roll} out of {chosen_max}")


def ooc_cmd_rollp(client, arg):
    """
    Roll a die privately. Same as /roll but the result is only shown to you and the CMs.
    Example: /roll 2d6 +5 would roll two 6-sided die and add 5 to every result.
    Rolls a 1d6 if blank
    X is the number of dice, Y is the maximum value on the die.
    Usage: /rollp [value/XdY] ["+5"/"-5"/"*5"/"/5"]
    """
    roll, num_dice, chosen_max, _modifiers, Sum = rtd(arg)

    client.send_ooc(
        f"[Hidden] You rolled {roll} out of {chosen_max}." + (f"\nThe total sum is {Sum}." if num_dice > 1 else "")
    )
    for c in client.area.owners:
        c.send_ooc(f"[{client.area.id}]{client.showname} secretly rolled {roll} out of {chosen_max}.")
    client.area.send_owner_command(
        f"[👉🎲] [{client.id}] {client.showname} secretly rolled:\n {roll} out of {chosen_max}."
        + (f"\nThe total sum is {Sum}." if num_dice > 1 else "")
    )
    database.log_area("rollp", client, client.area, message=f"{roll} out of {chosen_max}")


def ooc_cmd_notecard(client, arg):
    """
    Write a notecard that can only be revealed by a CM.
    Usage: /notecard <message>
    """
    if len(arg) == 0:
        if client.id in client.area.cards:
            client.send_ooc(
                f"Your current notecard is {client.area.cards[client.char_name]}. Usage: /notecard <message>"
            )
        else:
            client.send_ooc("No notecard found. Usage: /notecard <message>")
        return
    client.area.cards[client.char_name] = (client.showname, arg)
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} wrote a note card.")
    database.log_area("notecard", client, client.area)


@mod_only(area_owners=True)
def ooc_cmd_notecard_clear(client, arg):
    """
    Clear all notecards as a CM.
    Usage: /notecard_clear
    """
    client.area.cards.clear()
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} has cleared all the note cards in this area.")
    database.log_area("notecard_clear", client, client.area)


@mod_only(area_owners=True)
def ooc_cmd_notecard_reveal(client, arg):
    """
    Reveal all notecards and their owners.
    Set [clear] to 0 if you don't want the notecards to automatically clear after revealing.
    Usage: /notecard_reveal [clear]
    """
    if len(client.area.cards) == 0:
        raise ClientError("There are no cards to reveal in this area.")
    msg = "Note cards have been revealed:"
    for card_charname, card_data in client.area.cards.items():
        card_showname = card_data[0]
        card_msg = card_data[1]
        card_owner_display = f"[DC] {card_showname}"
        card_owner = client.server.client_manager.get_targets(client, TargetType.CHAR_NAME, card_charname, False)
        if len(card_owner) > 0:
            card_owner = card_owner[0]
            card_owner_display = f"[{card_owner.id}] {card_owner.showname}"
        msg += f"\n{card_owner_display}: {card_msg}"

    # Reveal the notecards in OOC!
    client.area.broadcast_ooc(msg)

    # Check if notecards auto-clear or not
    if arg.strip().lower() in ("0", "off", "false"):
        client.send_ooc("Use /notecard_clear for clearing.")
    else:
        client.area.cards.clear()
        client.area.broadcast_ooc("Notecards have been cleared.")

    database.log_area("notecard_reveal", client, client.area)


@mod_only(area_owners=True)
def ooc_cmd_notecard_check(client, arg):
    """
    Check all notecards and their owners privately with a message telling others you've done so.
    Usage: /notecard_check
    """
    if len(client.area.cards) == 0:
        raise ClientError("There are no notecards to check in this area.")
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} has checked the notecards in this area.")
    msg = "Notecards in this area:"
    for card_charname, card_data in client.area.cards.items():
        card_showname = card_data[0]
        card_msg = card_data[1]
        card_owner_display = f"[DC] {card_showname}"
        card_owner = client.server.client_manager.get_targets(client, TargetType.CHAR_NAME, card_charname, False)
        if len(card_owner) > 0:
            card_owner = card_owner[0]
            card_owner_display = f"[{card_owner.id}] {card_owner.showname}"
        msg += f"\n{card_owner_display}: {card_msg}"

    client.send_ooc(msg)
    client.send_ooc("Use /notecard_clear for clearing, or /notecard_reveal to reveal the results publicly.")
    database.log_area("notecard_check", client, client.area)


def ooc_cmd_vote(client, arg):
    """
    Cast a vote for a particular user that can only be revealed by a CM.
    Usage: /vote <id>
    """
    args = arg.split()
    if len(args) == 0:
        raise ArgumentError("Please provide a client ID. Usage: /vote <id>.")
    if client.char_name in [y for x in client.area.votes.values() for y in x]:
        raise ArgumentError("You already cast your vote! Wait on the CM to /vote_clear.")
    target = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), False)[0]
    client.area.votes.setdefault(target.char_name, []).append(client.char_name)
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} cast a vote.")
    database.log_area("vote", client, client.area)


@mod_only(area_owners=True)
def ooc_cmd_vote_clear(client, arg):
    """
    Clear all votes as a CM.
    Include [char_folder] (case-sensitive) to only clear a specific voter.
    Usage: /vote_clear [char_folder]
    """
    if arg != "":
        for value in client.area.votes.values():
            if arg in value:
                value.remove(arg)
                client.area.broadcast_ooc(f"[{client.id}] {client.showname} has cleared {arg}'s vote.")
                return
        raise ClientError(
            f"No vote was cast by {arg}! (This is case-sensitive - are you sure you spelled the voter character folder right?)"
        )
    client.area.votes.clear()
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} has cleared all the votes in this area.")
    database.log_area("vote_clear", client, client.area)


def get_vote_results(client, votes):
    def get_showname(target_name):
        """Helper function to convert a charname to showname format."""
        owners = client.server.client_manager.get_targets(client, TargetType.CHAR_NAME, target_name, False)
        if owners:
            owner = owners[0]
            return f"[{owner.id}] {owner.showname}"
        return target_name

    # Sort votes by count (ascending)
    sorted_votes = sorted(votes.items(), key=lambda x: len(x[1]))

    msg_lines = []
    max_votes = 0

    for candidate, voters in sorted_votes:
        # Process voters
        voter_names = [get_showname(voter) for voter in voters]
        voters_str = ", ".join(voter_names)

        # Process candidate
        candidate_name = get_showname(candidate)

        # Build vote line
        vote_count = len(voters)
        plural = "s" if vote_count > 1 else ""
        msg_lines.append(f"🗳️{vote_count} vote{plural} for {candidate_name}\n   ◽ Voted by {voters_str}.")

        # Track max votes
        if vote_count > max_votes:
            max_votes = vote_count

    # Find winners
    winners = [get_showname(k) for k, v in sorted_votes if len(v) == max_votes]

    # Add winner/tie message
    if len(winners) > 1:
        msg_lines.append(f"{', '.join(winners)} have tied for most votes.")
    else:
        msg_lines.append(f"{winners[0]} has most votes.")

    return "\n".join(msg_lines)


@mod_only(area_owners=True)
def ooc_cmd_vote_reveal(client, arg):
    """
    Reveal the number of votes, the voters and those with the highest amount of votes.
    Usage: /vote_reveal
    """
    if len(client.area.votes) == 0:
        raise ClientError("There are no votes to reveal in this area.")
    msg = "Votes have been revealed:"
    msg += get_vote_results(client, client.area.votes)
    client.area.broadcast_ooc(msg)

    # Check if votes auto-clear or not
    if arg.strip().lower() in ("0", "off", "false"):
        client.send_ooc("Use /vote_clear for clearing.")
    else:
        client.area.votes.clear()
        client.area.broadcast_ooc("Votes have been cleared.")

    database.log_area("vote_reveal", client, client.area)


@mod_only(area_owners=True)
def ooc_cmd_vote_check(client, arg):
    """
    Check the number of votes, the voters and those with the highest amount of votes privately with a message telling others you've done so.
    Usage: /vote_check
    """
    if len(client.area.votes) == 0:
        raise ClientError("There are no votes to check in this area.")
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} has checked the votes in this area.")
    msg = "Votes in this area:\n"
    msg += get_vote_results(client, client.area.votes)
    client.send_ooc(msg)
    client.send_ooc("Use /vote_clear for clearing, or /vote_reveal to reveal the results publicly.")
    database.log_area("vote_check", client, client.area)


@mod_only()
def ooc_cmd_rolla_reload(client, arg):
    """
    Reload ability dice sets from a configuration file.
    Usage: /rolla_reload
    """
    rolla_reload(client.area)
    client.send_ooc("Reloaded ability dice configuration.")
    database.log_area("rolla_reload", client, client.area)


def rolla_reload(area):
    try:
        import yaml

        with open("config/dice.yaml", "r") as dice:
            area.ability_dice = yaml.safe_load(dice)
    except Exception:
        raise ServerError("There was an error parsing the ability dice configuration. Check your syntax.")


def ooc_cmd_rolla_set(client, arg):
    """
    Choose the set of ability dice to roll.
    Usage: /rolla_set <name>
    """
    if not hasattr(client.area, "ability_dice"):
        rolla_reload(client.area)
    available_sets = ", ".join(client.area.ability_dice.keys())
    if len(arg) == 0:
        raise ArgumentError(f"You must specify the ability set name.\nAvailable sets: {available_sets}")
    elif arg not in client.area.ability_dice:
        raise ArgumentError(f"Invalid ability set '{arg}'.\nAvailable sets: {available_sets}")
    client.ability_dice_set = arg
    client.send_ooc(f"Set ability set to {arg}.")


def rolla(ability_dice):
    max_roll = ability_dice["max"] if "max" in ability_dice else 6
    roll = random.randint(1, max_roll)
    ability = ability_dice[roll] if roll in ability_dice else "Nothing happens."
    return (roll, max_roll, ability)


def ooc_cmd_rolla(client, arg):
    """
    Roll a specially labeled set of dice (ability dice).
    Usage: /rolla
    """
    if not hasattr(client.area, "ability_dice"):
        rolla_reload(client.area)
    if not hasattr(client, "ability_dice_set"):
        raise ClientError("You must set your ability set using /rolla_set <name>.")
    ability_dice = client.area.ability_dice[client.ability_dice_set]
    roll, max_roll, ability = rolla(ability_dice)
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} rolled a {roll} (out of {max_roll}): {ability}.")
    database.log_area("rolla", client, client.area, message=f"{roll} out of {max_roll}: {ability}")


def ooc_cmd_coinflip(client, arg):
    """
    Flip a coin. The result is shown publicly.
    Usage: /coinflip
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
    coin = ["heads", "tails"]
    flip = random.choice(coin)
    client.area.broadcast_ooc(f"[{client.id}] {client.showname} flipped a coin and got {flip}.")
    database.log_area("coinflip", client, client.area, message=flip)


def ooc_cmd_8ball(client, arg):
    """
    Answers a question. The result is shown publicly.
    Usage: /8ball <question>
    """

    arg = arg.strip()
    if len(arg) == 0:
        raise ArgumentError("You need to ask a question")
    if len(arg) > 128:
        raise ArgumentError("Your question is too long!")
    rolla_reload(client.area)
    ability_dice = client.area.ability_dice["8ball"]
    client.area.broadcast_ooc(
        f'{client.showname} asked the 8ball - "{arg}", and it responded: "{rolla(ability_dice)[2]}".'
    )


def ooc_cmd_rps(client, arg):
    """
    Starts a match of Rock Paper Scissors.
    If [choice] is not provided, view current RPS rules.
    Usage: /rps [choice]
    To abandon the match, use /rps cancel
    """
    # format:
    # [
    #   [a, b, c, ...] where 'a' beats 'b', 'c', ...
    # ]

    rps_rules = client.area.area_manager.rps_rules

    # Strip the input of blank spaces on edges
    arg = arg.strip()

    # If doing /rps by itself, simply tell the user the rules.
    if not arg:
        msg = "RPS rules:"
        for i, rule in enumerate(rps_rules):
            msg += f"\n  {i + 1}) "
            choice = rule[0]
            msg += choice
            if len(choice) > 1:
                losers = ", ".join(rule[1:])
                msg += f" beats {losers}"
        client.send_ooc(msg)
        return

    if arg.lower() in ["clear", "cancel"]:
        if client.rps_choice:
            client.area.broadcast_ooc(
                f"[{client.id}] {client.showname} no longer wants to play 🎲Rock Paper Scissors🎲... 🙁"
            )
        client.rps_choice = ""
        client.send_ooc("You cleared your choice.")
        return

    # List of our available choices
    choices = []
    for rule in rps_rules:
        rule = rule[0].lower()
        if rule not in choices:
            choices.append(rule)
    picked = ""
    for choice in choices:
        # Exact match, can't get better than this. Break out of the loop
        if arg.lower() == choice:
            picked = choice
            break
        # Fuzzy match, queue up our pick but look if we can get something better
        if arg.lower() in choice:
            picked = choice

    if picked not in choices:
        raise ArgumentError(f"Invalid choice! Available choices are: {', '.join(choices)}")

    # If we already have made a rps choice before, simply silently swap our choice.
    if client.rps_choice:
        client.rps_choice = picked
        client.send_ooc(f"Swapped your choice to {client.rps_choice}!")
        return

    # Set our Rock Paper Scissors choice
    client.rps_choice = picked

    # Loop through clients in area to see if they're waiting on the challenge
    # TODO: this method is gonna be bug-prone, please fix.
    target = None
    for c in client.area.clients:
        if c == client:
            continue
        if c.rps_choice:
            target = c
            break

    # Look for our opponent if none is present
    if not target:
        msg = f"[{client.id}] {client.showname} wants to play 🎲Rock Paper Scissors🎲!\n❕ Do /rps [choice] to challenge them! ❕"
        client.area.broadcast_ooc(msg)
        client.send_ooc(f"You picked {client.rps_choice}!")
        return

    # Start constructing our output message
    msg = "🎲Rock Paper Scissors🎲"
    msg += f"\n  ◽ [{target.id}] {target.showname} picks {target.rps_choice}!"
    msg += f"\n  ◽ [{client.id}] {client.showname} picks {client.rps_choice}!"

    # Calculate our winner
    a = target.rps_choice.lower()
    b = client.rps_choice.lower()
    winner = None
    for rule in rps_rules:
        rule = [r.lower() for r in rule]
        choice = rule[0]
        losers = []
        if len(rule) > 1:
            losers = rule[1:]
        if a in choice and b in losers:
            winner = target
            break
        elif b in choice and a in losers:
            winner = client
            break

    # Congratulate our winner or announce a tie
    if winner:
        msg += f"\n  🏆[{winner.id}] {winner.showname} WINS!!!🏆"
    else:
        msg += "\n  👔It's a tie!👔"

    # Announce the message!
    client.area.broadcast_ooc(msg)

    # Clear the game for our 2 contestants
    target.rps_choice = ""
    client.rps_choice = ""


@mod_only(area_owners=True)
def ooc_cmd_rps_rules(client, arg):
    """
    Review or change rps rules
    Usage:  /rps_rules - review current rules, indexed
            /rps_rules <add|new|+> [a beats b, c, d, ...] - add a new rule, or rules if the param is split by line break
            /rps_rules <del|remove|-> [index] - delete a rule at index
            /rps_rules <clear|clean|reset|wipe> - wipe all current rules
    """
    # client.area.area_manager.rps_rules

    # Strip the input of blank spaces on edges
    arg = arg.strip()

    # If doing /rps_rules by itself, simply tell the user the rules.
    if not arg:
        ooc_cmd_rps(client, "")
        return

    try:
        args = arg.split(maxsplit=1)
        action = args[0]
        param = ""
        if len(args) > 1:
            param = args[1]
        if action.lower() in ["add", "new", "+"]:
            rules = param.splitlines()
            for rule in rules:
                newrule = rule.split("beats")
                newrule = [newrule[0].strip()] + newrule[1].strip().split(",")
                newrule = [a.strip() for a in newrule]
                client.area.area_manager.rps_rules.append(newrule)
                client.send_ooc(f"Added a new rule: {rule}")
        elif action.lower() in ["del", "remove", "-"]:
            index = int(param) - 1
            if index < 0 or index >= len(client.area.area_manager.rps_rules):
                raise ArgumentError("Invalid index!")
            client.send_ooc(f"Deleted a rule: {client.area.area_manager.rps_rules[index]}")
            client.area.area_manager.rps_rules.pop(index)
        elif action.lower() in ["clear", "clean", "reset", "wipe"]:
            client.send_ooc("Deleted all rules.")
            client.area.area_manager.rps_rules.clear()
        else:
            raise ArgumentError("Invalid action!")
    except ValueError:
        raise ArgumentError("Invalid parameter!")


def ooc_cmd_timer(client, arg):
    """
    Manage a countdown timer in the current area. Note that timer of ID `0` is hub-wide. All other timer ID's are local to area.
    Anyone can check ongoing timers, their status and time left using `/timer <id>`, so `/timer 0`.
    `[time]` can be formated as `10m5s`, or `"10 minutes 5 seconds"` (quotes included) - full list of time formats: https://pypi.org/project/pytimeparse/
    You can optionally add or subtract time, like so: `/timer 0 +5s` to add `5` seconds to timer id `0`.
    `start` starts the previously set timer, so `/timer 0 start`.
    `pause` OR `stop` pauses the timer that's currently running, so `/timer 0 pause`.
    `unset` OR `hide` hides the timer for it to no longer show up, so `/timer 0 hide`.
    Commands can also be passed - /cmd is a command that you want to run when the timer expires. That command will be added to the stack of commands to run.
    For example, `/timer 0 /timer 0 hide` will hide the timer when it expires. Adding `/timer 0 /h hello there` will also say "hello there" in hub chat as your client.
    If you want to clear all commands, use `/timer <id> /clear`
    Usage:
    /timer <id> [+][time] [start|pause/stop|unset/hide]
    /timer <id> /cmd
    """

    args = shlex.split(arg)
    if len(args) < 1:
        msg = "Currently active timers:"
        # Hub timer
        timer = client.area.area_manager.timer
        if timer.set:
            if timer.started:
                msg += f"\nTimer 0 is at {timer.target - arrow.get()}"
            else:
                msg += f"\nTimer 0 is at {timer.static}"
        # Area timers
        for timer_id, timer in enumerate(client.area.timers):
            if timer.set:
                if timer.started:
                    msg += f"\nTimer {timer_id + 1} is at {timer.target - arrow.get()}"
                else:
                    msg += f"\nTimer {timer_id + 1} is at {timer.static}"
        client.send_ooc(msg)
        return
    # TI packet specification:
    # TI#TimerID#Type#Value#%
    # TimerID = from 0 to 4 (5 possible timers total)
    # Type 0 = start/resume/sync timer at time
    # Type 1 = pause timer at time
    # Type 2 = show timer
    # Type 3 = hide timer
    # Value = Time to set on the timer
    timer_id = int(args[0])
    if timer_id < 0 or timer_id > 20:
        raise ArgumentError("Invalid ID. Usage: /timer <id>")
    if timer_id == 0:
        timer = client.area.area_manager.timer
    else:
        timer = client.area.timers[timer_id - 1]
    if len(args) < 2:
        if timer.set:
            if timer.started:
                client.send_ooc(f"Timer {timer_id} is at {timer.target - arrow.get()}")
            else:
                client.send_ooc(f"Timer {timer_id} is at {timer.static}")
        else:
            client.send_ooc(f"Timer {timer_id} is unset.")
        return

    if client not in client.area.owners and not client.is_mod:
        raise ArgumentError("Only CMs or GMs can modify timers. Usage: /timer <id>")
    if timer_id == 0 and client not in client.area.area_manager.owners and not client.is_mod:
        raise ArgumentError("Only GMs can set hub-wide timer ID 0. Usage: /timer <id>")

    command_arg = args[1]

    duration_arg = args[1]
    duration = pytimeparse.parse(duration_arg)
    if duration is not None:
        if timer.set:
            if timer.started:
                if not (duration_arg[0] == "+" or duration < 0):
                    timer.target = arrow.get()
                timer.target = timer.target.shift(seconds=duration)
                timer.static = timer.target - arrow.get()
            else:
                if not (duration_arg[0] == "+" or duration < 0):
                    timer.static = datetime.timedelta(0)
                timer.static += datetime.timedelta(seconds=duration)
        else:
            timer.static = datetime.timedelta(seconds=abs(duration))
            timer.set = True
        if len(args) > 2:
            command_arg = args[2]

    if not timer.set:
        client.send_ooc(f"Timer {timer_id} is not set in this area.")
        return

    if command_arg == "start" and not timer.started:
        timer.target = timer.static + arrow.get()
        timer.started = True
        client.send_ooc(f"Starting timer {timer_id}.")
    elif command_arg in ("pause", "stop") and timer.started:
        timer.static = timer.target - arrow.get()
        timer.started = False
        client.send_ooc(f"Stopping timer {timer_id}.")
    elif command_arg in ("unset", "hide"):
        timer.set = False
        timer.started = False
        timer.static = None
        timer.target = None
        timer.commands.clear()
        if timer.schedule:
            timer.schedule.cancel()
        client.send_ooc(f"Timer {timer_id} unset and hidden.")
        if timer_id == 0:
            client.area.area_manager.send_timer_set_time(timer_id, None)
        else:
            client.area.send_timer_set_time(timer_id, None)
    elif args[1][0] == "/":
        full = " ".join(args[1:])[1:]
        if full == "":
            txt = f"Timer {timer_id} commands:"
            for command in timer.commands:
                txt += f"  \n/{command}"
            txt += "\nThey will be called once the timer expires."
            client.send_ooc(txt)
            return
        if full.lower() == "clear":
            timer.commands.clear()
            client.send_ooc(f"Clearing all commands for Timer {timer_id}.")
            return

        cmd = full.split(" ")[0]
        called_function = f"ooc_cmd_{cmd}"
        if len(client.server.command_aliases) > 0 and not hasattr(commands, called_function):
            if cmd in client.server.command_aliases:
                called_function = f"ooc_cmd_{client.server.command_aliases[cmd]}"
        if not hasattr(commands, called_function):
            client.send_ooc(f"[Timer {timer_id}] Invalid command: {cmd}. Use /help to find up-to-date commands.")
            return
        timer.commands.append(full)
        client.send_ooc(f"Adding command to Timer {timer_id}: /{full}")
        return

    # Send static time if applicable
    if timer.set:
        int(not timer.started)
        static_time = int(timer.static.total_seconds()) * 1000
        if timer_id == 0:
            client.area.area_manager.send_timer_set_time(timer_id, static_time, timer.started)
        else:
            client.area.send_timer_set_time(timer_id, static_time, timer.started)
        client.send_ooc(f"Timer {timer_id} is at {timer.static}")

        if timer_id == 0:
            timer.hub = client.area.area_manager
        else:
            timer.area = client.area

        timer.caller = client
        if timer.schedule:
            timer.schedule.cancel()
        if timer.started:
            timer.schedule = asyncio.get_running_loop().call_later(
                int(timer.static.total_seconds()), timer.timer_expired
            )


@mod_only(area_owners=True)
def ooc_cmd_demo(client, arg):
    """
    Usage:
    /demo <evidence_id> or /demo <evidence_name>
    Use /demo to stop demo
    """
    if arg == "":
        client.area.stop_demo()
        client.send_ooc("Stopping demo playback...")
        return
    if (time.time() * 1000 - client.last_demo_call) < 1000:
        client.send_ooc("Please wait a bit before calling /demo again!")
        return
    evidence = None
    if arg.isnumeric():
        arg = str(int(arg) - 1)
    for i, evi in enumerate(client.area.evi_list.evidences):
        if arg.lower() == evi.name.lower() or arg == str(i):
            evidence = evi
            break
    if not evidence:
        raise ArgumentError("Target evidence not found!")

    client.last_demo_call = time.time() * 1000
    client.area.demo.clear()

    desc = evidence.desc.replace("<num>", "#").replace("<and>", "&").replace("<percent>", "%").replace("<dollar>", "$")
    packets = desc.split("%")
    for packet in packets:
        p_args = packet.split("#")
        p_args[0] = p_args[0].strip()
        if p_args[0] in ["MS", "CT", "MC", "BN", "HP", "RT", "wait", "GM", "ST"]:
            client.area.demo += [p_args]
        elif p_args[0].startswith("/"):  # It's a command!
            p_args = packet.split(" ")
            p_args[0] = p_args[0].strip()
            client.area.demo += [p_args]
    for c in client.area.clients:
        if c in client.area.owners:
            c.send_ooc(f"Starting demo playback using evidence '{evidence.name}'...")

    client.area.play_demo(client)


@mod_only(area_owners=True)
def ooc_cmd_trigger(client, arg):
    """
    Set up a trigger for this area which, when fulfilled, will call the command.
    `trig` is the trigger keyword. Available keywords are 'join', 'leave' and 'present id' where id is the evidence ID.
    `cmd` is the standard command name, such as 'lock' to call the `lock` command when trigger is fulfilled.
    `arg(s)` are the arguments of the command, so in `bg default`, `default` is the argument
    CM's, GM's and Mods are ignored by triggers.
    Usage:
    /trigger trig cmd arg(s)
    """
    if arg == "":
        msg = "This area's triggers are:"
        for key, value in client.area.triggers.items():
            msg += f'\nCall "{value}" on {key}'
        msg = "\nEvidence triggers:"
        for evidence in client.area.evi_list.evidences:
            if "present" in evidence.triggers:
                value = evidence.triggers["present"]
                if value != "":
                    msg += f'\n💼{evidence.name}: Call "{value}" on present'
        client.send_ooc(msg)
        return
    if arg.lower().startswith("present "):
        args = arg.split(" ", 2)
        trig = args[0].lower()
        if len(args) <= 1:
            raise ArgumentError("Please provide target evidence!")
        _id = args[1]
        evidence = None
        if _id.isnumeric():
            _id = str(int(_id) - 1)
        for i, evi in enumerate(client.area.evi_list.evidences):
            if _id.lower() == evi.name.lower() or _id == str(i):
                evidence = evi
                break
        if not evidence:
            raise ArgumentError("Target evidence not found!")
        if len(args) <= 2:
            client.send_ooc(f'Call "{evidence.triggers[trig]}" on trigger "{trig}"')
            return
        val = args[2]
        evidence.triggers[trig] = val
        client.send_ooc(f'Changed to Call "{val}" on trigger "{trig}"')
    else:
        args = arg.split(" ", 1)
        trig = args[0].lower()
        if trig not in client.area.triggers:
            raise ArgumentError(f"Invalid trigger: {trig}")
        if len(args) <= 1:
            client.send_ooc(f'Call "{client.area.triggers[trig]}" on trigger "{trig}"')
            return
        val = args[1]
        client.area.triggers[trig] = val
        client.send_ooc(f'Changed to Call "{val}" on trigger "{trig}"')


def ooc_cmd_format_timer(client, arg):
    """
    - Format the timer in the current area or hub.
    - Example of format: Time Left: hh:mm
    - Default format: hh:mm:ss.zzz
    Usage: /format_timer <Timer_iD> <Format>
    """
    args = shlex.split(arg)
    try:
        args[0] = int(args[0])
    except (ValueError, IndexError):
        return
    if args[0] == 0:
        if client.is_mod or client in client.area.area_manager.owners:
            timer = client.area.area_manager.timer
        else:
            client.send_ooc("You cannot change timer 0 format if you are not GM")
            return
    else:
        if client.is_mod or client in client.area.area_manager.owners or client in client.area.owners:
            timer = client.area.timers[args[0] - 1]
        else:
            client.send_ooc("You cannot change timer format if you are at least CM")
            return
    timer.format = " ".join(args[1:])
    if timer.format == "":
        timer.format = "hh:mm:ss.zzz"
        client.send_ooc("Resetting timer format to default.")
    if timer.set:
        if timer.started:
            current_time = timer.target - arrow.get()
            current_time = int(current_time.total_seconds()) * 1000
        else:
            current_time = int(timer.static.total_seconds()) * 1000
        if args[0] == 0:
            client.area.area_manager.send_timer_set_time(args[0], current_time, timer.started)
        else:
            client.area.send_timer_set_time(args[0], current_time, timer.started)
    client.send_ooc(f"Timer {args[0]} format: '{timer.format}'")


def ooc_cmd_timer_interval(client, arg):
    """
    Set timer interval
    If timer interval is not written than will show default timer interval (16ms)
    Example: /timer_interval 1 15m
    Usage: /timer_interval <Timer_ID> <Interval>
    """
    args = shlex.split(arg)
    try:
        args[0] = int(args[0])
    except (ValueError, IndexError):
        raise ArgumentError("Timer ID should be an integer")
    if args[0] == 0:
        if client.is_mod or client in client.area.area_manager.owners:
            timer = client.area.area_manager.timer
        else:
            client.send_ooc("You cannot change timer 0 interval if you are not GM")
            return
    else:
        if client.is_mod or client in client.area.area_manager.owners or client in client.area.owners:
            timer = client.area.timers[args[0] - 1]
        else:
            client.send_ooc("You cannot change timer interval if you are at least CM")
            return
    try:
        if len(args) == 1:
            timer.interval = 16
        else:
            timer.interval = pytimeparse.parse(args[1]) * 1000
    except (TypeError, ValueError):
        raise ArgumentError("Interval value not valid!")
    if timer.set:
        client.send_timer_set_interval(args[0], timer)
    client.send_ooc(f"Timer {args[0]} interval is set to '{args[1]}'")


def ooc_cmd_ooc_actions(client, arg):
    """
    Enable or disable IC actions being broadcast to OOC as well.
    tog can be `on`, `off` or empty.
    Usage: /ooc_actions [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError("This command can only take one argument ('on' or 'off') or no arguments at all!")
    if arg:
        if arg == "on":
            client.ooc_actions = True
        elif arg == "off":
            client.ooc_actions = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.ooc_actions = not client.ooc_actions
    stat = "no longer see"
    if client.ooc_actions:
        stat = "now see"
    client.send_ooc(f"You will {stat} actions in OOC.")
