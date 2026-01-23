import yaml
import random
import os
import shlex

from server.client_manager import ClientManager
from server.constants import derelative

from . import mod_only

__all__ = [
    "ooc_cmd_choose_fighter",
    "ooc_cmd_info_fighter",
    "ooc_cmd_create_fighter",
    "ooc_cmd_create_move",
    "ooc_cmd_modify_stat",
    "ooc_cmd_delete_fighter",
    "ooc_cmd_delete_move",
    "ooc_cmd_battle_config",
    "ooc_cmd_fight",
    "ooc_cmd_use_move",
    "ooc_cmd_battle_info",
    "ooc_cmd_refresh_battle",
    "ooc_cmd_remove_fighter",
    "ooc_cmd_surrender",
    "ooc_cmd_skip_move",
    "ooc_cmd_force_skip_move",
    "ooc_cmd_create_guild",
    "ooc_cmd_info_guild",
    "ooc_cmd_join_guild",
    "ooc_cmd_leave_guild",
    "ooc_cmd_battle_effects",
    "ooc_cmd_close_guild",
]


battle_effects = [
    "atkraise",
    "sparaise",
    "defraise",
    "spdraise",
    "atkdown",
    "defdown",
    "spadown",
    "spddown",
    "speraise",
    "spedown",
    "heal",
    "poison",
    "paralysis",
    "atkall",
    "multishot",
    "atkraiseally",
    "defraiseally",
    "sparaiseally",
    "spdraiseally",
    "speraiseally",
    "stealatk",
    "stealdef",
    "stealspa",
    "stealspd",
    "stealspe",
    "stealmana",
    "burn",
    "freeze",
    "stunned",
    "confused",
    "enraged",
    "sleep",
    "healstatus",
]


def send_info_fighter(client):
    """
    Prepare the message about fighter info
    """
    msg = f"\n👤 {client.battle.fighter} 👤:\n"
    if client.battle.status is not None:
        msg += f"Status 🌈: {client.battle.status}\n"
    msg += f"\nHP 💗: {round(client.battle.hp, 2)}/{client.battle.maxhp}\nMANA 💧: {round(client.battle.mana, 2)}\nATK 🗡️: {round(client.battle.atk, 2)}\nDEF 🛡️: {round(client.battle.defe, 2)}\nSPA ✨: {round(client.battle.spa, 2)}\nSPD 🔮: {round(client.battle.spd, 2)}\nSPE 💨: {round(client.battle.spe, 2)}\n\n"
    for move in client.battle.moves:
        move_id = client.battle.moves.index(move)
        msg += f"🌠 [{move_id}]{move.name} 🌠:\nManaCost 💧: {move.cost}\nType 💠: {move.type}\nPower 💪: {move.power}\nAccuracy 🔎: {move.accuracy}%\n"
        if move.effect != []:
            msg += "Effects 🔰:\n"
            for effect in move.effect:
                msg += f"- {effect}\n"
        msg += "\n"
    client.send_ooc(msg)


def send_stats_fighter(client):
    """
    Prepare the message about fighter stats
    """
    msg = f"\n👤 {client.battle.fighter} 👤:\n"
    if client.battle.status is not None:
        msg += f"Status 🌈: {client.battle.status}\n"
    msg += f"\nHP 💗: {round(client.battle.hp, 2)}/{client.battle.maxhp}\nMANA 💧: {round(client.battle.mana, 2)}\nATK 🗡️: {round(client.battle.atk, 2)}\nDEF 🛡️: {round(client.battle.defe, 2)}\nSPA ✨: {round(client.battle.spa, 2)}\nSPD 🔮: {round(client.battle.spd, 2)}\nSPE 💨: {round(client.battle.spe, 2)}\n\n"
    client.send_ooc(msg)


def ooc_cmd_choose_fighter(client, arg):
    """
    Allow you to choose a fighter from the list of the server.
    You will receive its stats and its moves.
    Usage: /choose_fighter NameFighter
    """
    if f"{arg.lower()}.yaml" in os.listdir("storage/battlesystem"):
        with open(f"storage/battlesystem/{arg.lower()}.yaml", "r", encoding="utf-8") as c_load:
            char = yaml.safe_load(c_load)
            client.battle = ClientManager.BattleChar(client, arg.lower(), char)
        send_info_fighter(client)
    else:
        client.send_ooc("No fighter has this name!")


def ooc_cmd_info_fighter(client, arg):
    """
    Send info about your fighter.
    Usage: /info_fighter
    """
    if client.battle is not None:
        send_info_fighter(client)
    else:
        client.send_ooc("You have to choose a fighter first!")


def ooc_cmd_create_fighter(client, arg):
    """
    Allow you to create a fighter and to customize its stats.
    Usage: /create_fighter FighterName HP MANA ATK DEF SPA SPD SPE
    """
    args = shlex.split(arg)

    if len(args) > 8:
        client.send_ooc("Too many arguments...\nUsage: /create_fighter FighterName HP MANA ATK DEF SPA SPD SPE")
        return

    if len(args) < 8:
        client.send_ooc("Not enough arguments...\nUsage: /create_fighter FighterName HP MANA ATK DEF SPA SPD SPE")
        return

    if (
        float(args[1]) <= 0
        or float(args[2]) < 0
        or float(args[3]) < 0
        or float(args[4]) < 0
        or float(args[5]) < 0
        or float(args[6]) < 0
        or float(args[7]) < 0
    ):
        client.send_ooc(
            "mana, atk, def, spa, spd, spe have to be greater than or equal to zero\nhp has to be greater than zero\nUsage: /create_fighter FighterName HP MANA ATK DEF SPA SPD SPE"
        )
        return

    fighter_list = os.listdir("storage/battlesystem")

    path = derelative(args[0].lower())
    if f"{path}.yaml" in fighter_list:
        client.send_ooc("This fighter has already been created.")
        return

    fighter = {}
    fighter["HP"] = float(args[1])
    fighter["MANA"] = float(args[2])
    fighter["ATK"] = float(args[3])
    fighter["DEF"] = float(args[4])
    fighter["SPA"] = float(args[5])
    fighter["SPD"] = float(args[6])
    fighter["SPE"] = float(args[7])
    fighter["Moves"] = []

    with open(
        f"storage/battlesystem/{path}.yaml",
        "w",
        encoding="utf-8",
    ) as c_save:
        yaml.dump(fighter, c_save)
        client.send_ooc(f"{path} has been created!")


def ooc_cmd_create_move(client, arg):
    """
    Allow you to create a move for a fighter.
    You have to choose a fighter first!
    MovesType: Atk or Spa
    Usage: /create_move MoveName ManaCost MovesType Power Accuracy Effects
    """
    if client.battle is None:
        client.send_ooc("You have to choose a figher to create a move.\n /choose_fighter FighterName")
        return

    args = shlex.split(arg)

    if len(args) < 5:
        client.send_ooc(
            "Not enough arguments...\nUsage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    if float(args[1]) < 0:
        client.send_ooc(
            "ManaCost has to be greater than or equal to zero.\nUsage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    if float(args[3]) < 0:
        client.send_ooc(
            "Power has to be greater than or equal to zero.\nUsage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    if float(args[4]) <= 0 or float(args[4]) > 100:
        client.send_ooc(
            "Accuracy should be a integer between 1 and 100\nUsage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    if args[2].lower() not in ["atk", "spa"]:
        client.send_ooc(
            "Move's Type should be atk or spa!\nUsage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    with open(f"storage/battlesystem/{client.battle.fighter}.yaml", "r", encoding="utf-8") as c_load:
        char = yaml.safe_load(c_load)

        move_list = []
        for i in range(0, len(char["Moves"])):
            move_list.append(char["Moves"][i]["Name"])

        if args[0].lower() in move_list:
            client.send_ooc("This move has already been created.")
            return

        char["Moves"].append({})
        index = len(char["Moves"]) - 1
        char["Moves"][index]["Name"] = args[0].lower()
        char["Moves"][index]["ManaCost"] = float(args[1])
        char["Moves"][index]["MovesType"] = args[2].lower()
        char["Moves"][index]["Power"] = float(args[3])
        char["Moves"][index]["Accuracy"] = float(args[4])
        char["Moves"][index]["Effects"] = []
        for i in range(5, len(args)):
            if args[i].lower() in battle_effects:
                char["Moves"][index]["Effects"].append(args[i].lower())
        with open(
            f"storage/battlesystem/{client.battle.fighter}.yaml",
            "w",
            encoding="utf-8",
        ) as c_save:
            yaml.dump(char, c_save)

        client.send_ooc(f"{args[0]} has been added!")
        client.battle = ClientManager.BattleChar(client, client.battle.fighter, char)
        guild = None
        for g in client.area.battle_guilds:
            if client in client.area.battle_guilds[g]:
                guild = g

        client.battle.guild = guild


@mod_only(hub_owners=True)
def ooc_cmd_modify_stat(client, arg):
    """
    Allow you to modify fighter's stats.
    Usage: /modify_stat FighterName Stat Value
    """
    args = shlex.split(arg)

    path = derelative(args[0].lower())
    if f"{path}.yaml" not in os.listdir("storage/battlesystem"):
        client.send_ooc("No fighter has this name!")
        return

    if args[1].lower() not in ["hp", "mana", "atk", "def", "spa", "spd", "spe"]:
        client.send_ooc("You could just modify this stats:\nhp, mana, atk, def, spa, spd, spe")
        return

    if float(args[2]) < 0:
        client.send_ooc("The value have to be a number greater than or equal to zero")
        return

    with open(f"storage/battlesystem/{path}.yaml", "r", encoding="utf-8") as c_load:
        char = yaml.safe_load(c_load)
        char[args[1].upper()] = float(args[2])
        with open(f"storage/battlesystem/{path}.yaml", "w", encoding="utf-8") as c_save:
            yaml.dump(char, c_save)
    client.send_ooc(f"{path}'s {args[1]} has been modified. To check the changes choose again this fighter")


@mod_only(hub_owners=True)
def ooc_cmd_delete_fighter(client, arg):
    """
    Allow you to delete a fighter.
    Usage: /delete_move FighterName
    """
    if f"{arg.lower()}.yaml" in os.listdir("storage/battlesystem"):
        os.remove(f"storage/battlesystem/{arg.lower()}.yaml")
        client.send_ooc(f"{arg} has been deleted!")
    else:
        client.send_ooc(f"{arg} is not found in the fighter server list.")


@mod_only(hub_owners=True)
def ooc_cmd_delete_move(client, arg):
    """
    Delete a move from a fighter.
    You have to choose a fighter first!
    Usage: /delete_move MoveName
    """

    if client.battle is None:
        client.send_ooc("You have to choose the fighter first")
        return

    with open(f"storage/battlesystem/{client.battle.fighter}.yaml", "r", encoding="utf-8") as c_load:
        char = yaml.safe_load(c_load)
        move_list = []
        for i in range(0, len(char["Moves"])):
            move_list.append(char["Moves"][i]["Name"])
        if arg.lower() in move_list:
            index = move_list.index(arg.lower())
            char["Moves"].pop(index)
            with open(
                f"storage/battlesystem/{client.battle.fighter}.yaml",
                "w",
                encoding="utf-8",
            ) as c_save:
                yaml.dump(char, c_save)

            client.battle = ClientManager.BattleChar(client, client.battle.fighter, char)
            guild = None
            for g in client.area.battle_guilds:
                if client in client.area.battle_guilds[g]:
                    guild = g

            client.battle.guild = guild
            client.send_ooc(f"{arg} has been deleted!")
        else:
            client.send_ooc(f"{arg} is not found in the fighter moves")


@mod_only(hub_owners=True)
def ooc_cmd_battle_config(client, arg):
    """
    Allow you to customize some battle settings.
    Usage: /custom_battle <parameter> <value>
    """
    if arg == "":
        client.send_ooc(
            "paralysis_rate, critical_rate, critical_bonus, bonus_malus, poison_damage, show_hp, min_multishot, max_multishot, burn_damage, freeze_damage, confusion_rate, enraged_bonus, stolen_stat"
        )
        return
    args = arg.split(" ")
    if args[0].lower() == "paralysis_rate":
        client.area.battle_paralysis_rate = int(args[1])
    elif args[0].lower() == "critical_rate":
        client.area.battle_critical_rate = int(args[1])
    elif args[0].lower() == "critical_bonus":
        client.area.battle_critical_bonus = float(args[1])
    elif args[0].lower() == "bonus_malus":
        client.area.battle_bonus_malus = float(args[1])
    elif args[0].lower() == "poison_damage":
        client.area.battle_poison_damage = float(args[1])
    elif args[0].lower() == "min_multishot":
        client.area.battle_min_multishot = int(args[1])
    elif args[0].lower() == "max_multishot":
        client.area.battle_max_multishot = int(args[1])
    elif args[0].lower() == "burn_damage":
        client.area.battle_burn_damage = float(args[1])
    elif args[0].lower() == "freeze_damage":
        client.area.battle_freeze_damage = float(args[1])
    elif args[0].lower() == "confusion_rate":
        client.area.battle_confusion_rate = int(args[1])
    elif args[0].lower() == "enraged_bonus":
        client.area.battle_enraged_bonus = float(args[1])
    elif args[0].lower() == "stolen_stat":
        client.area.battle_stolen_stat = float(args[1])
    elif args[1].lower() in ["true", "false"] and args[0].lower() == "show_hp":
        if args[1].lower() == "true":
            client.area.battle_show_hp = True
        else:
            client.area.battle_show_hp = False
    else:
        client.send_ooc("value is not valid")
        return
    client.send_ooc(f"{args[0].lower()} has been changed to {args[1]}")


def send_battle_info(client):
    """
    Prepare the message about battle info
    """
    msg = "\n⚔️🛡️ Battle Fighters Info 🛡️⚔️:\n"
    for guild in client.area.battle_guilds:
        msg += f"\n⛩{guild} GUILD⛩:\n"
        for client in client.area.battle_guilds[guild]:
            if client not in client.area.fighters:
                continue

            if client.battle.selected_move == -1:
                emoji = "🔎"
            else:
                emoji = "⚔️"

            if client.area.battle_show_hp:
                show_hp = f": {round(client.battle.hp * 100 / client.battle.maxhp, 2)}%"
            else:
                show_hp = ""

            msg += f"{emoji} [{client.id}]{client.battle.fighter} ({client.showname}){show_hp} {emoji}\n"
        msg += "\n"

    for client in client.area.fighters:
        if client.battle.guild is None:
            if client.battle.selected_move == -1:
                emoji = "🔎"
            else:
                emoji = "⚔️"

            if client.area.battle_show_hp:
                show_hp = f": {round(client.battle.hp * 100 / client.battle.maxhp, 2)}%"
            else:
                show_hp = ""

            msg += f"{emoji} [{client.id}]{client.battle.fighter} ({client.showname}){show_hp} {emoji}\n"
    return msg


def ooc_cmd_battle_info(client, arg):
    """
    Send you info about the battle.
    Usage: /battle_info
    """
    if client in client.area.fighters:
        msg = send_battle_info(client)
        client.send_ooc(msg)
    else:
        client.send_ooc("You are not fighting!")


def ooc_cmd_fight(client, arg):
    """
    Allow you to join the battle or rejoin if you disconnected!
    Usage: /fight
    """
    if len(client.area.fighters) > 0 and client.area.battle_started:
        free_fighters = {c.battle.fighter: c for c in client.area.fighters if c.battle.current_client is not None}
        if client in client.area.fighters:
            index = client.area.fighters.index(client)
            client.battle = client.area.fighters[index].battle
            client.battle.current_client = client
            return
        if len(free_fighters) > 0:
            fighter, target = random.choice(list(free_fighters.items()))
            if client.battle is not None and client.battle.fighter in free_fighters:
                client.battle = free_fighters[client.battle.fighter].battle
            else:
                client.battle = target.battle

            client.battle.current_client = client
            if client.battle.guild is not None:
                index = client.area.battle_guilds[client.battle.guild].index(target)
                client.area.battle_guilds[client.battle.guild][index] = client
            client.area.fighters.remove(target)
            client.area.fighters.append(client)
            msg = send_battle_info(client)
            battle_send_ic(client, msg=f"~{client.battle.fighter}~ is ready to fight (reconnected)")
            for client in client.area.fighters:
                client.send_ooc(msg)
            return

    if not client.area.can_battle:
        client.send_ooc("You cannot fight in this area!")
        return
    if client.battle is None:
        client.send_ooc("You have to choose a fighter to start a battle!")
        return
    if client in client.area.fighters:
        client.send_ooc("You are already in battle!")
        return
    if client.area.battle_started:
        client.send_ooc("The battle is already started!")
        return
    client.area.fighters.append(client)
    msg = send_battle_info(client)
    for client in client.area.fighters:
        client.send_ooc(msg)
    client.area.broadcast_ooc(f"⚔️{client.battle.fighter} ({client.showname}) is ready to fight!⚔️")
    client.area.area_manager.char_list[client.char_id]
    battle_send_ic(client, msg=f"~{client.battle.fighter}~ is ready to fight")


@mod_only(hub_owners=True)
def ooc_cmd_refresh_battle(client, arg):
    """
    Refresh the battle
    Usage: /refresh_battle
    """
    for c in client.area.fighters:
        c.battle.selected_move = -1
        c.target = None
    client.area.fighters = []
    client.area.battle_started = False
    client.send_ooc("The battle has been refreshed!")


def ooc_cmd_surrender(client, arg):
    """
    A command to surrend from the current battle.
    Usage: /surrender
    """
    if client in client.area.fighters:
        if client.battle.selected_move == -1:
            client.area.fighters.remove(client)
        else:
            client.battle.hp = 0
            client.battle.selected_move = -1
            client.battle.target = None
        battle_send_ic(client, msg=f"~{client.battle.fighter}~ decides to surrend", offset=100)
        with open(
            f"storage/battlesystem/{client.battle.fighter}.yaml",
            "r",
            encoding="utf-8",
        ) as c_load:
            char = yaml.safe_load(c_load)
            client.battle = ClientManager.BattleChar(client, client.battle.fighter, char)
        guild = None
        for g in client.area.battle_guilds:
            if client in client.area.battle_guilds[g]:
                guild = g

        client.battle.guild = guild
        if len(client.area.fighters) == 0:
            client.area.battle_started = False
    else:
        client.send_ooc("You are not fighting in this moment!")


@mod_only(hub_owners=True)
def ooc_cmd_remove_fighter(client, arg):
    """
    Force a fighter to leave the battle.
    Usage: /remove_fighter Target_ID
    """
    fighter_ids = {c.id: c for c in client.area.fighters}
    if int(arg) in fighter_ids:
        target = fighter_ids[int(arg)]
        if target.battle.selected_move == -1:
            client.area.fighters.remove(target)
        else:
            target.battle.hp = 0
            target.battle.selected_move = -1
            target.battle.target = None
        battle_send_ic(
            client,
            msg=f"~{target.battle.fighter}~ ran out of hp! (forced to leave the battle)",
            offset=100,
        )
        with open(
            f"storage/battlesystem/{target.battle.fighter}.yaml",
            "r",
            encoding="utf-8",
        ) as c_load:
            char = yaml.safe_load(c_load)
            target.battle = ClientManager.BattleChar(target, target.battle.fighter, char)
        guild = None
        for g in target.area.battle_guilds:
            if target in target.area.battle_guilds[g]:
                guild = g

        target.battle.guild = guild
        if len(client.area.fighters) == 0:
            client.area.battle_started = False
    else:
        client.send_ooc("Target not found!")


@mod_only(hub_owners=True)
def ooc_cmd_force_skip_move(client, arg):
    """
    Force a fighter to skip the turn
    Usage: /force_skip_move Target_ID
    """

    fighter_ids = {c.id: c for c in client.area.fighters}
    if int(arg) not in fighter_ids:
        client.send_ooc("The target is not in the fighter list")
        return

    target = fighter_ids[int(arg)]

    if target.battle.selected_move == -1:
        target.area.num_selected_move += 1

    target.battle.selected_move = -2
    target.send_ooc("You have been forced to skip the turn")
    client.send_ooc(f"{target.battle.fighter} has been forced to skip the turn")
    client.area.broadcast_ooc(f"{target.battle.fighter} has choosen a move")

    if client.area.num_selected_move == len(client.area.fighters):
        client.area.fighters = start_battle_animation(client.area)
        client.area.num_selected_move = 0
        if not client.area.battle_started:
            client.area.battle_started = True
        if len(client.area.fighters) == 0:
            client.area.battle_started = False


def ooc_cmd_skip_move(client, arg):
    """
    Allow you to skip the turn
    Usage: /skip_move
    """
    if client not in client.area.fighters:
        client.send_ooc("You cannot skip the turn if you are not in the fight!")
        return
    if client.battle.selected_move != -1:
        client.send_ooc("You already selected a move!")
        return

    client.battle.selected_move = -2
    client.area.num_selected_move += 1
    client.send_ooc("You have choosen to skip the turn")
    client.area.broadcast_ooc(f"{client.battle.fighter} has choosen a move")

    if client.area.num_selected_move == len(client.area.fighters):
        client.area.fighters = start_battle_animation(client.area)
        client.area.num_selected_move = 0
        if not client.area.battle_started:
            client.area.battle_started = True
        if len(client.area.fighters) == 0:
            client.area.battle_started = False


def ooc_cmd_close_guild(client, arg):
    """
    Allow GM to close all guilds if arg is "", or to close a specific guild is arg is GuildName
    Usage: /close_guild <GuildName>
    """
    if arg == "":
        for guild in client.area.battle_guilds:
            for c in client.area.battle_guilds[guild]:
                c.battle.guild = None
        client.area.battle_guilds = {}
        client.area.broadcast_ooc("All guilds have been closed!")
    elif arg in client.area.battle_guilds:
        for c in client.area.battle_guilds[arg]:
            c.send_ooc(f"'{arg}' Guild has been closed")
        client.area.battle_guilds.pop(arg)
    else:
        client.send_ooc("Guild not found!")


def ooc_cmd_battle_effects(client, arg):
    """
    Show all available battle effects
    Usage: /battle_effects
    """
    msg = "Available Battle Effects:\n"
    for effect in battle_effects:
        msg += f"- {effect}\n"
    client.send_ooc(msg)


def ooc_cmd_leave_guild(client, arg):
    """
    Allow you to leave your current guid
    Usage: /leave_guild <Target_ID>
    """
    if arg == "":
        if client.battle.guild is None:
            client.send_ooc("You are not in any guilds!")
            return

        guild = client.battle.guild
        client.area.battle_guilds[guild].remove(client)
        client.send_ooc("You have been removed from the current guild")
        if client.area.battle_guilds[guild] == []:
            client.area.battle_guild.pop(guild)
        client.battle.guild = None
    else:
        if client in client.area.area_manager.owners:
            area_ids = {c.id: c for c in client.area.clients}
            if int(arg) in area_ids:
                target = area_ids[int(arg)]
                if target.battle is None or target.battle.guild is None:
                    client.send_ooc("Target has not a fighter or is not in a guild!")
                    return
                guild = target.battle.guild
                client.area.battle_guilds[guild].remove(target)
                if len(client.area.battle_guilds[guild]) == 0:
                    client.area.battle_guilds.pop(guild)
                target.battle.guild = None
                client.send_ooc(f"Target has been removed from '{guild}' Guild")
                target.send_ooc(f"You have been removed from '{guild}' Guild")
            else:
                client.send_ooc("Target not found!")
        elif client == client.area.battle_guilds[client.battle.guild][0]:
            guild_ids = {c.id: c for c in client.area.battle_guilds[client.battle.guild]}
            if int(arg) in guild_ids:
                target = guild_ids[int(arg)]
                guild = target.battle.guild
                client.area.battle_guilds[guild].remove(target)
                if len(client.area.battle_guilds[guild]) == 0:
                    client.area.battle_guilds.pop(guild)
                target.battle.guild = None
                client.send_ooc(f"Target has been removed from '{guild}' Guild")
                target.send_ooc(f"You have been removed from '{guild}' Guild")
            else:
                client.send_ooc("Target not found!")
        else:
            client.send_ooc("You are not a GM or a Guild Leader")


def ooc_cmd_join_guild(client, arg):
    """
    Allow the guild leader to let a fighter to join the guild
    Usage: /join_guild <Target_ID>
    """
    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return

    if client.battle.guild is None:
        client.send_ooc("You are not in any guilds!")
        return

    guild = client.battle.guild

    if client != client.area.battle_guilds[guild][0]:
        client.send_ooc("You are not the guild leader, you cannot choose who can join to the guild.")
        return

    area_ids = {c.id: c for c in client.area.clients}

    if int(arg) not in area_ids:
        client.send_ooc("Target not found!")
        return

    target = area_ids[int(arg)]

    if target.battle is None:
        client.send_ooc(f"{client.showname} has to choose a fighter first!")
        return

    if target.battle.guild is not None:
        client.send_ooc(f"{client.battle.fighter} is already in a guild!")
        return

    if target in client.area.battle_guilds[guild]:
        client.send_ooc(f"{client.battle.fighter} is already in this guild!")
        return

    client.area.battle_guilds[guild].append(target)
    target.battle.guild = guild
    client.send_ooc(f"{target.battle.fighter} joined to the {guild} Guild!")
    target.send_ooc(f"You joined to the {guild} Guild!")
    for client in client.area.battle_guilds[guild]:
        send_info_guild(client)


def ooc_cmd_create_guild(client, arg):
    """
    Allow you to create a guild
    Usage: /create_guild <NameGuild>
    """
    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return

    if arg in client.area.battle_guilds:
        client.send_ooc("There is already a guild with this name!")
        return

    client.area.battle_guilds[arg] = []
    client.area.battle_guilds[arg].append(client)
    client.battle.guild = arg
    client.send_ooc(f"{arg} Guild has been created!")
    send_info_guild(client)


def ooc_cmd_info_guild(client, arg):
    """
    Send info about your guild
    Usage: /info_guild
    """
    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return

    if client.battle.guild is None:
        client.send_ooc("You are not in any guilds!")
        return

    send_info_guild(client)


def send_info_guild(client):
    guild = client.battle.guild

    guild_leader = client.area.battle_guilds[guild][0]

    msg = f"\n⚔️🛡️{guild} GUILD🛡️⚔️:\n\nGuild Leader: ⛩[{guild_leader.id}]{guild_leader.battle.fighter} ({guild_leader.showname})⛩"

    if len(client.area.battle_guilds[guild]) > 1:
        msg += "\n\n👤Members👤:\n\n"
        for fighter in client.area.battle_guilds[guild]:
            if fighter != guild_leader:
                msg += f"⚔️[{fighter.id}]{fighter.battle.fighter} ({fighter.showname})⚔️\n"

    client.send_ooc(msg)


def ooc_cmd_use_move(client, arg):
    """
    This command will let you use a move during a battle!
    AttAll moves don't need a target!
    Usage: /use_move MoveName/Move_ID Target_ID
    """
    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return
    if client not in client.area.fighters:
        client.send_ooc("You are not ready to fight!")
        return
    if client.battle.selected_move != -1:
        client.send_ooc("You already selected a move!")
        return
    if client.battle.current_client is None:
        client.battle.current_client = client

    args = shlex.split(arg)
    if args[0].isnumeric():
        if int(args[0]) > len(client.battle.moves):
            client.send_ooc("There is no move with that ID!")
            return

        move_id = int(args[0])
        args[0] = client.battle.moves[move_id].name
    else:
        moves_list = [move.name for move in client.battle.moves]

        if args[0].lower() not in moves_list:
            client.send_ooc("There is no move with this name!")
            return

        move_id = moves_list.index(args[0].lower())

    if client.battle.moves[move_id].cost > client.battle.mana:
        client.send_ooc("You don't have enough mana to use this move!")
        return

    if len(args) == 2:
        fighter_id_list = {c.id: c for c in client.area.fighters}
        if int(args[1]) in fighter_id_list:
            client.battle.target = fighter_id_list[int(args[1])]
            client.battle.selected_move = move_id
            client.area.num_selected_move += 1
            client.battle.mana += -client.battle.moves[move_id].cost
            client.send_ooc(f"You have choosen {args[0].lower()}")
            client.area.broadcast_ooc(f"{client.battle.fighter} has choosen a move")
        else:
            client.send_ooc("Your target is not in the fighter list")
    elif "atkall" in client.battle.moves[move_id].effect:
        client.battle.target = "all"
        client.battle.selected_move = move_id
        client.area.num_selected_move += 1
        client.battle.mana += -client.battle.moves[move_id].cost
        client.send_ooc(f"You have choosen {args[0].lower()}")
        client.area.broadcast_ooc(f"{client.battle.fighter} has choosen a move")
    else:
        client.send_ooc("Not enough argument to attack")
    if client.area.num_selected_move == len(client.area.fighters):
        client.area.fighters = start_battle_animation(client.area)
        client.area.num_selected_move = 0
        if not client.area.battle_started:
            client.area.battle_started = True
        if len(client.area.fighters) == 0:
            client.area.battle_started = False


def battle_send_ic(client, msg, effect="", shake=0, offset=0):
    """
    A function used to send battle information in IC
    effect: statdown, statup, poison, paralysis, lifeup, attack, specialattack
    shake: screeenshake 0 = False, 1 = True
    offset: 0 = alive, 100 = dead
    Choosen_color = 3
    """

    if offset != 0:
        offset = 100
    else:
        offset = client.offset_pair

    if effect == "":
        sfx = ""
    else:
        sfx = f"sfx-{effect}"

    if client.charid_pair != -1:
        client_ids = {c.char_id: c for c in client.area.clients}
        if client.charid_pair in client_ids:
            target = client_ids[client.charid_pair]
            other_offset = target.offset_pair
            other_emote = target.last_sprite
            other_flip = target.flip
            other_folder = target.claimed_folder
        else:
            client.charid_pair = -1

    if client.charid_pair == -1:
        other_offset = 0
        other_emote = ""
        other_flip = 0
        other_folder = ""

    client.area.send_ic(
        pre=client.last_pre,
        folder=client.claimed_folder,
        anim=client.last_sprite,
        msg=msg,
        pos=client.pos,
        emote_mod=1,
        flip=client.flip,
        color=3,
        charid_pair=client.charid_pair,
        offset_pair=offset,
        other_offset=other_offset,
        other_emote=other_emote,
        other_flip=other_flip,
        other_folder=other_folder,
        screenshake=shake,
        effect=f"{effect}|BattleEffects|{sfx}",
    )


def start_battle_animation(area):
    # first of all we sort the fighters compared to their speed.
    fighter_speed = {client: client.battle.spe for client in area.fighters}
    sorted_fighter_speed = sorted(fighter_speed.items(), key=lambda x: x[1])
    sorted_fighter_speed = dict(sorted_fighter_speed)
    area.fighters = list(sorted_fighter_speed.keys())

    # Let all fighters do their moves
    for client in area.fighters:
        if client.battle.hp > 0:
            # check if a fighter skipped the turn
            if client.battle.selected_move == -2:
                battle_send_ic(client, msg=f"~{client.battle.fighter}~ decides to skip the turn")
                continue

            if client.battle.status == "stunned":
                client.battle.status = None
                battle_send_ic(client, msg=f"~{client.battle.fighter}~ is stunned and cannot fight")
                continue

            if client.battle.status == "confused":
                confused = random.randint(1, client.area.battle_confusion_rate)
                if confused == 1:
                    client.battle.status = None
                    battle_send_ic(client, msg=f"~{client.battle.fighter}~ snaps out of confusion")
                elif confused == client.area.battle_confusion_rate:
                    battle_send_ic(
                        client,
                        msg=f"~{client.battle.fighter}~ is confused and misses the target",
                        effect="confused",
                    )
                    continue
                else:
                    battle_send_ic(
                        client,
                        msg=f"~{client.battle.fighter}~ is confused but focuses on the target",
                        effect="confused",
                    )

            if client.battle.status is not None and "sleep" in client.battle.status:
                if client.battle.status == "sleep-1":
                    battle_send_ic(
                        client,
                        msg=f"~{client.battle.fighter}~ is sleeping",
                        effect="sleep",
                    )
                    client.battle.status = "sleep-2"
                    continue
                elif client.battle.status == "sleep-2":
                    battle_send_ic(
                        client,
                        msg=f"~{client.battle.fighter}~ is sleeping",
                        effect="sleep",
                    )
                    client.battle.status = "sleep-3"
                    continue
                else:
                    battle_send_ic(client, msg=f"~{client.battle.fighter}~ wakes up")

            move = client.battle.moves[client.battle.selected_move]

            # check if the fighter misses the move
            miss = random.randint(1, 100)
            if move.accuracy < miss:
                battle_send_ic(client, msg=f"~{client.battle.fighter}~ misses the target")
                continue

            # check if the fighter is paralysed
            paralysis = random.randint(1, area.battle_paralysis_rate)
            if paralysis == area.battle_paralysis_rate and client.battle.status == "paralysis":
                battle_send_ic(
                    client,
                    msg=f"~{client.battle.fighter}~ is affected by paralysis and cannot fight",
                    effect="paralysis",
                    shake=1,
                )
                continue

            # creating target list
            if "atkall" in move.effect:
                if (
                    "heal" in move.effect
                    or "healstatus" in move.effect
                    or "atkraiseally" in move.effect
                    or "defraiseally" in move.effect
                    or "sparaiseally" in move.effect
                    or "spdraiseally" in move.effect
                    or "speraiseally" in move.effect
                ):
                    if client.battle.guild is None:
                        targets = [c for c in client.area.fighters]
                    else:
                        targets = [
                            c for c in client.area.battle_guilds[client.battle.guild] if c in client.area.fighters
                        ]
                else:
                    if client.battle.guild is None:
                        targets = [c for c in client.area.fighters if c != client]
                    else:
                        targets = [
                            c for c in client.area.fighters if c not in client.area.battle_guilds[client.battle.guild]
                        ]
                    if "multishot" in move.effect:
                        shots = random.randint(
                            client.area.battle_min_multishot,
                            client.area.battle_max_multishot,
                        )
                        targets = random.choices(targets, shots)
            elif "multishot" in move.effect and "atkall" not in move.effect:
                shots = random.randint(client.area.battle_min_multishot, client.area.battle_max_multishot)
                targets = []
                for i in range(0, shots):
                    targets.append(client.battle.target)
            else:
                targets = [client.battle.target]

            # send in ic the message 'fighter uses this move'
            battle_send_ic(client, msg=f"~{client.battle.fighter}~ uses ~{move.name}~")

            # Ally move
            if "heal" in move.effect:
                for target in targets:
                    if target.battle.hp <= 0:
                        if len(targets) == 1:
                            battle_send_ic(
                                client,
                                msg="and tries to help but the target is already down",
                            )
                        continue
                    if "heal" in move.effect:
                        # calculate heal
                        if "atk" == move.type:
                            heal = (move.power + client.battle.atk) * 0.25
                        else:
                            heal = (move.power + client.battle.spa) * 0.25

                        target.battle.hp += heal

                        # check if heal+hp is greater than maxhp
                        if target.battle.hp > target.battle.maxhp:
                            target.battle.hp = target.battle.maxhp

                        # send ic healing move
                        if target == client:
                            battle_send_ic(
                                client,
                                msg=f"and heals itself of ~{heal}~ hp",
                                effect="lifeup",
                            )
                        else:
                            battle_send_ic(
                                target,
                                msg=f"and heals ~{target.battle.fighter}~ of ~{heal}~ hp",
                                effect="lifeup",
                            )

                    if "healstatus" in move.effect:
                        if target.battle.status is None:
                            battle_send_ic(
                                target,
                                f"and tries to remove status from ~{target.battle.fighter}~ but ~{target.battle.fighter}~ is healthy",
                            )
                        else:
                            status = target.battle.status
                            if "sleep" in status:
                                status = "sleep"
                            target.battle.status = None
                            battle_send_ic(
                                target,
                                f"and removed {status} from ~{target.battle.fighter}~",
                            )
                            if status == "burn":
                                target.battle.spd = target.battle.spd * area.battle_bonus_malus
                                target.battle.defe = target.battle.defe * area.battle_bonus_malus

                    if "atkraiseally" in move.effect:
                        target.battle.atk = target.battle.atk * area.battle_bonus_malus
                        battle_send_ic(
                            target,
                            msg=f" and raises the attack of ~{target.battle.fighter}~",
                            effect="statup",
                        )

                    if "defraiseally" in move.effect:
                        target.battle.defe = target.battle.defe * area.battle_bonus_malus
                        battle_send_ic(
                            target,
                            msg=f" and raises the defense of ~{target.battle.fighter}~",
                            effect="statup",
                        )

                    if "sparaiseally" in move.effect:
                        target.battle.spa = target.battle.spa * area.battle_bonus_malus
                        battle_send_ic(
                            target,
                            msg=f" and raises the special attack of ~{target.battle.fighter}~",
                            effect="statup",
                        )

                    if "spdraiseally" in move.effect:
                        target.battle.spd = target.battle.spd * area.battle_bonus_malus
                        battle_send_ic(
                            target,
                            msg=f" and raises the special defense of ~{target.battle.fighter}~",
                            effect="statup",
                        )

                    if "speraiseally" in move.effect:
                        target.battle.spe = target.battle.spe * area.battle_bonus_malus
                        battle_send_ic(
                            target,
                            msg=f" and raises the speed of ~{target.battle.fighter}~",
                            effect="statup",
                        )

                continue

            # damage move
            for target in targets:
                if target.battle.hp <= 0:
                    if len(targets) == 1:
                        battle_send_ic(client, msg="but the target is already down")
                    continue

                # calculate damage
                if move.type == "atk":
                    if target.battle.defe != 0:
                        damage = move.power * client.battle.atk / target.battle.defe
                    else:
                        damage = target.battle.maxhp
                    effect = "attack"
                else:
                    if target.battle.spd != 0:
                        damage = move.power * client.battle.spa / target.battle.spd
                    else:
                        damage = target.battle.maxhp
                    effect = "specialattack"

                damage = round(damage, 2)

                # calculate critical damage
                critical = random.randint(1, area.battle_critical_rate)
                critical_message = ""
                if critical == area.battle_critical_rate:
                    critical_message = " with a critical"
                    damage = damage * area.battle_critical_bonus
                target.battle.hp += -damage

                if client.battle.status == "enraged":
                    client.battle.status = None
                    damage = damage * area.battle_enraged_bonus
                    battle_send_ic(client, msg="focuses all strenght")

                # send ic damage move
                if damage == 0:
                    battle_send_ic(
                        target,
                        msg=f"on ~{target.battle.fighter}~",
                        effect=effect,
                        shake=1,
                    )
                else:
                    battle_send_ic(
                        target,
                        msg=f"and attacks ~{target.battle.fighter}~{critical_message} dealing a damage of ~{damage}~",
                        effect=effect,
                        shake=1,
                    )

                if target.battle.status is not None and "sleep" in target.battle.status:
                    target.battle.status = None
                    battle_send_ic(target, msg=f"~{target.battle.fighter}~ wakes up")

                # check malus move effects
                if "atkdown" in move.effect:
                    target.battle.atk = target.battle.atk / area.battle_bonus_malus
                    battle_send_ic(
                        target,
                        msg=f"The attack of ~{target.battle.fighter}~ goes down",
                        effect="statdown",
                    )
                if "defdown" in move.effect:
                    target.battle.defe = target.battle.defe / area.battle_bonus_malus
                    battle_send_ic(
                        target,
                        msg=f"The defense of ~{target.battle.fighter}~ goes down",
                        effect="statdown",
                    )
                if "spadown" in move.effect:
                    target.battle.spa = target.battle.spa / area.battle_bonus_malus
                    battle_send_ic(
                        target,
                        msg=f"The special attack of ~{target.battle.fighter}~ goes down",
                        effect="statdown",
                    )
                if "spddown" in move.effect:
                    target.battle.spd = target.battle.spd / area.battle_bonus_malus
                    battle_send_ic(
                        target,
                        msg=f"The special defense of ~{target.battle.fighter}~ goes down",
                        effect="statdown",
                    )
                if "spedown" in move.effect:
                    target.battle.spe = target.battle.spe / area.battle_bonus_malus
                    battle_send_ic(
                        target,
                        msg=f"The speed of ~{target.battle.fighter}~ goes down",
                        effect="statdown",
                    )
                if "stealatk" in move.effect:
                    client.battle.atk += target.battle.atk / area.battle_stolen_stat
                    target.battle.atk += -target.battle.atk / area.battle_stolen_stat
                    battle_send_ic(
                        target,
                        msg=f"~{client.battle.fighter}~ steals the attack of ~{target.battle.fighter}~",
                        effect="stealstat",
                    )
                if "stealdef" in move.effect:
                    client.battle.defe += target.battle.defe / area.battle_stolen_stat
                    target.battle.defe += -target.battle.defe / area.battle_stolen_stat
                    battle_send_ic(
                        target,
                        msg=f"~{client.battle.fighter}~ steals the defense of ~{target.battle.fighter}~",
                        effect="stealstat",
                    )
                if "stealspa" in move.effect:
                    client.battle.spa += target.battle.spa / area.battle_stolen_stat
                    target.battle.spa += -target.battle.spa / area.battle_stolen_stat
                    battle_send_ic(
                        target,
                        msg=f"~{client.battle.fighter}~ steals the special attack of ~{target.battle.fighter}~",
                        effect="stealstat",
                    )
                if "stealspd" in move.effect:
                    client.battle.spd += target.battle.spd / area.battle_stolen_stat
                    target.battle.spd += -target.battle.spd / area.battle_stolen_stat
                    battle_send_ic(
                        target,
                        msg=f"~{client.battle.fighter}~ steals the special defense of ~{target.battle.fighter}~",
                        effect="stealstat",
                    )
                if "stealspe" in move.effect:
                    client.battle.spe += target.battle.spe / area.battle_stolen_stat
                    target.battle.spe += -target.battle.spe / area.battle_stolen_stat
                    battle_send_ic(
                        target,
                        msg=f"~{client.battle.fighter}~ steals the speed of ~{target.battle.fighter}~",
                        effect="stealstat",
                    )
                if "stealmana" in move.effect:
                    client.battle.mana += target.battle.mana / area.battle_stolen_stat
                    target.battle.mana += -target.battle.mana / area.battle_stolen_stat
                    battle_send_ic(
                        target,
                        msg=f"~{client.battle.fighter}~ steals mana from ~{target.battle.fighter}~",
                        effect="stealstat",
                    )
                if "poison" in move.effect:
                    if target.battle.status is None:
                        target.battle.status = "poison"
                        battle_send_ic(
                            target,
                            msg=f"~{target.battle.fighter}~ is affected by poisoning",
                            effect="poison",
                            shake=1,
                        )
                if "paralysis" in move.effect:
                    if target.battle.status is None:
                        target.battle.status = "paralysis"
                        battle_send_ic(
                            target,
                            msg=f"~{target.battle.fighter}~ is affected by paralysis",
                            effect="paralysis",
                            shake=1,
                        )
                if "burn" in move.effect:
                    if target.battle.status is None:
                        target.battle.status = "burn"
                        battle_send_ic(
                            target,
                            msg=f"~{target.battle.fighter}~ is burned",
                            effect="burn",
                            shake=1,
                        )
                        target.battle.spd = target.battle.spd / area.battle_bonus_malus
                        target.battle.defe = target.battle.defe / area.battle_bonus_malus
                        battle_send_ic(
                            target,
                            msg=f"and ~{target.battle.fighter}~'s defensive statistics go down",
                            effect="statdown",
                        )
                if "freeze" in move.effect:
                    if target.battle.status is None:
                        target.battle.status = "freeze"
                        battle_send_ic(
                            target,
                            msg=f"~{target.battle.fighter}~ is frozen",
                            effect="freeze",
                            shake=1,
                        )
                if "stunned" in move.effect:
                    if target.battle.status is None:
                        target.battle.status = "stunned"
                        battle_send_ic(
                            target,
                            msg=f"~{target.battle.fighter}~ is stunned",
                            shake=1,
                        )
                if "confused" in move.effect:
                    if target.battle.status is None:
                        target.battle.status = "confused"
                        battle_send_ic(
                            target,
                            msg=f"~{target.battle.fighter}~ is confused",
                            effect="confused",
                        )
                if "sleep" in move.effect:
                    if target.battle.status is None:
                        target.battle.status = "sleep-1"
                        battle_send_ic(
                            target,
                            msg=f"~{target.battle.fighter}~ is sleeping",
                            effect="sleep",
                        )
                # check if target is dead
                if target.battle.hp <= 0:
                    battle_send_ic(
                        target,
                        msg=f"~{target.battle.fighter}~ ran out of hp!",
                        offset=100,
                    )

            # check bonus move effect
            if "atkraise" in move.effect:
                client.battle.atk = client.battle.atk * area.battle_bonus_malus
                battle_send_ic(
                    client,
                    msg=f"The attack of ~{client.battle.fighter}~ goes up",
                    effect="statup",
                )
            if "defraise" in move.effect:
                client.battle.defe = client.battle.defe * area.battle_bonus_malus
                battle_send_ic(
                    client,
                    msg=f"The defense of ~{client.battle.fighter}~ goes up",
                    effect="statup",
                )
            if "sparaise" in move.effect:
                client.battle.spa = client.battle.spa * area.battle_bonus_malus
                battle_send_ic(
                    client,
                    msg=f"The special attack of ~{client.battle.fighter}~ goes up",
                    effect="statup",
                )
            if "spdraise" in move.effect:
                client.battle.spd = client.battle.spd * area.battle_bonus_malus
                battle_send_ic(
                    client,
                    msg=f"The special defense of ~{client.battle.fighter}~ goes up",
                    effect="statup",
                )
            if "speraise" in move.effect:
                client.battle.spe = client.battle.spe * area.battle_bonus_malus
                battle_send_ic(
                    client,
                    msg=f"The speed of ~{client.battle.fighter}~ goes up",
                    effect="statup",
                )

            if "enraged" in move.effect:
                client.battle.status = "enraged"
                battle_send_ic(
                    client,
                    msg=f"~{client.battle.fighter}~ is preparing for the next attack",
                    effect="enraged",
                )

    # check poisoned, burned and frozen fighters
    for client in area.fighters:
        if client.battle.hp <= 0:
            continue
        client.area.area_manager.char_list[client.char_id]
        if client.battle.status == "poison" and client.battle.hp > 0:
            client.battle.hp += -client.battle.maxhp / area.battle_poison_damage
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is affected by poisoning and loses {client.battle.maxhp / area.battle_poison_damage} hp",
                effect="poison",
                shake=1,
            )
        if client.battle.status == "burn" and client.battle.hp > 0:
            client.battle.hp += -client.battle.maxhp / area.battle_burn_damage
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is burned and loses {client.battle.maxhp / area.battle_burn_damage} hp",
                effect="burn",
                shake=1,
            )
        if client.battle.status == "freeze" and client.battle.hp > 0:
            client.battle.hp += -client.battle.maxhp / area.battle_freeze_damage
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is frozen and loses {client.battle.maxhp / area.battle_freeze_damage} hp",
                effect="freeze",
                shake=1,
            )
            target.battle.spe = target.battle.spe / area.battle_bonus_malus
            battle_send_ic(
                target,
                msg=f"and ~{target.battle.fighter}~'s speed goes down",
                effect="statdown",
            )
        if client.battle.hp <= 0 and client.battle.status in [
            "poison",
            "burn",
            "freeze",
        ]:
            battle_send_ic(client, msg=f"~{client.battle.fighter}~ ran out of hp!", offset=100)

    # check dead fighters and unselect move and target
    for client in list(area.fighters):
        # Unselect move and target
        client.battle.selected_move = -1
        client.battle.target = None

        # check dead fighters
        if client.battle.hp <= 0:
            area.fighters.remove(client)
            with open(
                f"storage/battlesystem/{client.battle.fighter}.yaml",
                "r",
                encoding="utf-8",
            ) as c_load:
                char = yaml.safe_load(c_load)
                client.battle = ClientManager.BattleChar(client, client.battle.fighter, char)
            guild = None
            for g in client.area.battle_guilds:
                if client in client.area.battle_guilds[g]:
                    guild = g

            client.battle.guild = guild

    # check if there is a winner or everyone is dead
    if len(area.fighters) == 1:
        winner = area.fighters[0]
        battle_send_ic(winner, msg=f"~{winner.battle.fighter}~ wins the battle!")
        with open(f"storage/battlesystem/{winner.battle.fighter}.yaml", "r", encoding="utf-8") as c_load:
            char = yaml.safe_load(c_load)
            winner.battle = ClientManager.BattleChar(winner, winner.battle.fighter, char)
        guild = None
        for g in winner.area.battle_guilds:
            if winner in winner.area.battle_guilds[g]:
                guild = g

        winner.battle.guild = guild
        area.fighters = []
    elif len(area.fighters) == 0:
        battle_send_ic(client, msg="~Everyone~ is down...", offset=100)
        area.fighters = []
    else:
        # check if there is a winner guild
        winner_guild = None
        guilds = [c.battle.guild for c in area.fighters]
        if len(set(guilds)) == 1 and guilds[0] is not None:
            guild = guilds[0]
            winner_guild = client.area.battle_guilds[guild]
            battle_send_ic(winner_guild[0], msg=f"~{guild}~ wins the battle!")
            area.fighters = []
            for winner in winner_guild:
                with open(
                    f"storage/battlesystem/{winner.battle.fighter}.yaml",
                    "r",
                    encoding="utf-8",
                ) as c_load:
                    char = yaml.safe_load(c_load)
                    winner.battle = ClientManager.BattleChar(winner, winner.battle.fighter, char)
                guild = None
                for g in winner.area.battle_guilds:
                    if winner in winner.area.battle_guilds[g]:
                        guild = g

                winner.battle.guild = guild
        else:
            # prepare for the next turn
            for client in area.fighters:
                send_stats_fighter(client)
                msg = send_battle_info(client)
                client.send_ooc(msg)
    return area.fighters
