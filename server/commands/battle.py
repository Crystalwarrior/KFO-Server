import yaml
import random
import os
import shlex

from server.client_manager import ClientManager

from . import mod_only
from .. import commands

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
    "healally",
    "atkall",
]


def send_info_fighter(client):
    """
    Prepare the message about fighter info
    """
    msg = f"\n👤 {client.battle.fighter} 👤:\n"
    if client.battle.status != None:
        msg += f"Status 🌈: {client.battle.status}\n"
    msg += f"\nHP 💗: {round(client.battle.hp,2)}/{client.battle.maxhp}\nATK 🗡️: {round(client.battle.atk,2)}\nDEF 🛡️: {round(client.battle.defe,2)}\nSPA ✨: {round(client.battle.spa,2)}\nSPD 🔮: {round(client.battle.spd,2)}\nSPE 💨: {round(client.battle.spe,2)}\n\n"
    for move in client.battle.moves:
        move_id = client.battle.moves.index(move)
        msg += f"🌠 [{move_id}]{move.name} 🌠:\nType 💠: {move.type}\nPower 💪: {move.power}\nAccuracy 🔎: {move.accuracy}%\n"
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
    if client.battle.status != None:
        msg += f"Status 🌈: {client.battle.status}\n"
    msg += f"\nHP 💗: {round(client.battle.hp,2)}/{client.battle.maxhp}\nATK 🗡️: {round(client.battle.atk,2)}\nDEF 🛡️: {round(client.battle.defe,2)}\nSPA ✨: {round(client.battle.spa,2)}\nSPD 🔮: {round(client.battle.spd,2)}\nSPE 💨: {round(client.battle.spe,2)}\n\n"
    client.send_ooc(msg)


def ooc_cmd_choose_fighter(client, arg):
    """
    Allow you to choose a fighter from the list of the server.
    You will receive its stats and its moves.
    Usage: /choose_fighter NameFighter
    """
    if f"{arg.lower()}.yaml" in os.listdir("storage/battlesystem"):
        with open(
            f"storage/battlesystem/{arg.lower()}.yaml", "r", encoding="utf-8"
        ) as c_load:
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
    Usage: /create_fighter FighterName HP ATK DEF SPA SPD SPE
    """
    args = shlex.split(arg)

    if len(args) > 7:
        client.send_ooc(
            "Too many arguments...\nUsage: /create_fighter FighterName HP ATK DEF SPA SPD SPE"
        )
        return

    if len(args) < 7:
        client.send_ooc(
            "Not enough arguments...\nUsage: /create_fighter FighterName HP ATK DEF SPA SPD SPE"
        )
        return

    if (
        float(args[1]) <= 0
        or float(args[2]) <= 0
        or float(args[3]) <= 0
        or float(args[4]) <= 0
        or float(args[5]) <= 0
        or float(args[6]) <= 0
    ):
        client.send_ooc(
            "hp, atk, def, spa, spd, spe have to be greater than zero!\nUsage: /create_fighter FighterName HP ATK DEF SPA SPD SPE"
        )
        return

    fighter_list = os.listdir("storage/battlesystem")

    if f"{args[0].lower()}.yaml" in fighter_list:
        client.send_ooc("This fighter has already been created.")
        return

    fighter = {}
    fighter["HP"] = float(args[1])
    fighter["ATK"] = float(args[2])
    fighter["DEF"] = float(args[3])
    fighter["SPA"] = float(args[4])
    fighter["SPD"] = float(args[5])
    fighter["SPE"] = float(args[6])
    fighter["Moves"] = []

    with open(
        f"storage/battlesystem/{args[0].lower()}.yaml",
        "w",
        encoding="utf-8",
    ) as c_save:
        yaml.dump(fighter, c_save)
        client.send_ooc(f"{args[0]} has been created!")


def ooc_cmd_create_move(client, arg):
    """
    Allow you to create a move for a fighter.
    You have to choose a fighter first!
    MovesType: Atk or Spa
    Usage: /create_move MoveName MovesType Power Accuracy Effects
    """
    if client.battle is None:
        client.send_ooc(
            "You have to choose a figher to create a move.\n /choose_fighter FighterName"
        )
        return

    args = shlex.split(arg)

    if len(args) < 4:
        client.send_ooc(
            "Not enough arguments...\nUsage: /create_move MoveName MovesType Power Accuracy Effects"
        )
        return

    if float(args[2]) <= 0:
        client.send_ooc(
            "Power has to be greater than 0.\nUsage: /create_move MoveName MovesType Power Accuracy Effects"
        )
        return

    if float(args[3]) <= 0 or float(args[3]) > 100:
        client.send_ooc(
            "Accuracy should be a integer between 1 and 100\nUsage: /create_move MoveName MovesType Power Accuracy Effects"
        )
        return

    if args[1].lower() not in ["atk", "spa"]:
        client.send_ooc(
            "Move's Type should be atk or spa!\nUsage: /create_move MoveName MovesType Power Accuracy Effects"
        )
        return

    with open(
        f"storage/battlesystem/{client.battle.fighter}.yaml", "r", encoding="utf-8"
    ) as c_load:
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
        char["Moves"][index]["MovesType"] = args[1].lower()
        char["Moves"][index]["Power"] = float(args[2])
        char["Moves"][index]["Accuracy"] = float(args[3])
        char["Moves"][index]["Effects"] = []
        for i in range(4, len(args)):
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


@mod_only(hub_owners=True)
def ooc_cmd_modify_stat(client, arg):
    """
    Allow you to modify fighter's stats.
    Usage: /modify_stat FighterName Stat Value
    """
    args = shlex.split(arg)
    if f"{args[0].lower()}.yaml" not in os.listdir("storage/battlesystem"):
        client.send_ooc("No fighter has this name!")
        return

    if args[1].lower() not in ["hp", "atk", "def", "spa", "spd", "spe"]:
        client.send_ooc(
            "You could just modify this stats:\nhp, atk, def, spa, spd, spe"
        )
        return

    if float(args[2]) <= 0:
        client.send_ooc("The value have to be a number greater than zero")
        return

    with open(
        f"storage/battlesystem/{args[0].lower()}.yaml", "r", encoding="utf-8"
    ) as c_load:
        char = yaml.safe_load(c_load)
        char[args[1].upper()] = float(args[2])
        with open(
            f"storage/battlesystem/{args[0].lower()}.yaml", "w", encoding="utf-8"
        ) as c_save:
            yaml.dump(char, c_save)
    client.send_ooc(
        f"{args[0]}'s {args[1]} has been modified. To check the changes choose again this fighter"
    )


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
    
    with open(
        f"storage/battlesystem/{client.battle.fighter}.yaml", "r", encoding="utf-8"
    ) as c_load:
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

            client.battle = ClientManager.BattleChar(
                client, client.battle.fighter, char
            )
            client.send_ooc(f"{arg} has been deleted!")
        else:
            client.send_ooc(f"{arg} is not found in the fighter moves")


@mod_only(hub_owners=True)
def ooc_cmd_battle_config(client, arg):
    """
    Allow you to customize some battle settings.
    parameters: paralysis_rate, critical_rate, critical_bonus, bonus_malus, poison_damage
    Usage: /battle_config parameter value
    """
    args = arg.split(" ")
    if args[1].isdigit:
        if args[0].lower() == "paralysis_rate":
            client.area.battle_paralysis_rate = int(args[1])
        if args[0].lower() == "critical_rate":
            client.area.battle_critical_rate = int(args[1])
        if args[0].lower() == "critical_bonus":
            client.area.battle_critical_bonus = float(args[1])
        if args[0].lower() == "bonus_malus":
            client.area.battle_bonus_malus = float(args[1])
        if args[0].lower() == "poison_damage":
            client.area.battle_poison_damage = float(args[1])
        client.send_ooc(f"{args[0].lower()} has been changed to {args[1]}")
    elif args[1].lower() in ["true", "false"] and args[0].lower() == "show_hp":
        if args[1].lower() == "true":
            client.area.battle_show_hp = True
        else:
            client.area.battle_show_hp = False
        client.send_ooc(f"{args[0].lower()} has been changed to {args[1].lower()}")
    else:
        client.send_ooc("value is not a digit")


def send_battle_info(client):
    """
    Prepare the message about battle info
    """
    msg = "\n⚔️🛡️ Battle Fighters Info 🛡️⚔️:\n\n"
    for client in client.area.fighters:
        if client.battle.selected_move == -1:
            emoji = "🔎"
        else:
            emoji = "⚔️"

        if client.area.battle_show_hp:
            show_hp = f": {round(client.battle.hp*100/client.battle.maxhp,2)}%"
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
    Allow you to join the battle!
    Usage: /fight
    """
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
    client.area.broadcast_ooc(
        f"⚔️{client.battle.fighter} ({client.showname}) is ready to fight!⚔️"
    )
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
        client.area.send_ic(
            pre=client.last_sprite,
            msg=f"~{client.battle.fighter}~ decides to surrend",
            pos=client.pos,
            flip=client.flip,
            color=3,
            offset_pair=100,
        )
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
        target = client.area.fighters[int(arg)]
        if target.battle.selected_move == -1:
            client.area.fighters.remove(target)
        else:
            target.battle.hp = 0
            target.battle.selected_move = -1
            target.battle.target = None
        client.area.send_ic(
            pre=target.last_sprite,
            msg=f"~{target.battle.fighter}~ ran out of hp! (forced to leave the battle)",
            pos=target.pos,
            flip=target.flip,
            color=3,
            offset_pair=100,
        )
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
        if len(client.area.fighters) < 2:
            client.area.fighters = []
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
    client.send_ooc(f"You have choosen to skip the turn")
    client.area.broadcast_ooc(f"{client.battle.fighter} has choosen a move")

    if client.area.num_selected_move == len(client.area.fighters):
        client.area.fighters = start_battle_animation(client.area)
        client.area.num_selected_move = 0
        if not client.area.battle_started:
            client.area.battle_started = True
        if len(client.area.fighters) < 2:
            client.area.fighters = []
            client.area.battle_started = False


def ooc_cmd_use_move(client, arg):
    """
    This command will let you use a move during a battle!
    Heal and AttAll moves don't need a target!
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
        
    if len(args) == 2:
        fighter_id_list = {c.id: c for c in client.area.fighters}
        if int(args[1]) in fighter_id_list:
            client.battle.target = fighter_id_list[int(args[1])]
            client.battle.selected_move = move_id
            client.area.num_selected_move += 1
            client.send_ooc(f"You have choosen {args[0].lower()}")
            client.area.broadcast_ooc(f"{client.battle.fighter} has choosen a move")
        else:
            client.send_ooc("Your target is not in the fighter list")
    elif "heal" in client.battle.moves[move_id].effect:
        client.battle.target = client
        client.battle.selected_move = move_id
        client.area.num_selected_move += 1
        client.send_ooc(f"You have choosen {args[0].lower()}")
        client.area.broadcast_ooc(f"{client.battle.fighter} has choosen a move")
    elif "atkall" in client.battle.moves[move_id].effect:
        client.battle.target = "all"
        client.battle.selected_move = move_id
        client.area.num_selected_move += 1
        client.send_ooc(f"You have choosen {args[0].lower()}")
        client.area.broadcast_ooc(f"{client.battle.fighter} has choosen a move")
    else:
        client.send_ooc("Not enough argument to attack")
    if client.area.num_selected_move == len(client.area.fighters):
        client.area.fighters = start_battle_animation(client.area)
        client.area.num_selected_move = 0
        if not client.area.battle_started:
            client.area.battle_started = True
        if len(client.area.fighters) < 2:
            client.area.fighters = []
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
        sfx=sfx,
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
                battle_send_ic(
                    client, msg=f"~{client.battle.fighter}~ decides to skip the turn"
                )
                continue
                
            move = client.battle.moves[client.battle.selected_move]

            # check if the fighter misses the move
            miss = random.randint(1, 100)
            if move.accuracy < miss:
                battle_send_ic(
                    client, msg=f"~{client.battle.fighter}~ misses the target"
                )
                continue

            # check if the fighter is paralysed
            paralysis = random.randint(1, area.battle_paralysis_rate)
            if (
                paralysis == area.battle_paralysis_rate
                and client.battle.status == "paralysis"
            ):
                battle_send_ic(
                    client,
                    msg=f"~{client.battle.fighter}~ is affected by paralysis and cannot fight",
                    effect="paralysis",
                    shake=1,
                )
                continue

            # creating target list
            if "atkall" in move.effect:
                targets = list(area.fighters)
                targets.remove(client)
            else:
                targets = [client.battle.target]

            # send in ic the message 'fighter uses this move'
            battle_send_ic(client, msg=f"~{client.battle.fighter}~ uses ~{move.name}~")

            # heal move
            if "heal" in move.effect or "healally" in move.effect:
                if client.battle.target.battle.hp <= 0:
                    battle_send_ic(
                        client, msg=f"and tries to heal but the target is already dead"
                    )
                else:
                    # calculate heal
                    if "atk" == move.type:
                        heal = (move.power + client.battle.atk) * 0.25
                    else:
                        heal = (move.power + client.battle.spa) * 0.25

                    client.battle.target.battle.hp += heal

                    # check if heal+hp is greater than maxhp
                    if (
                        client.battle.target.battle.hp
                        > client.battle.target.battle.maxhp
                    ):
                        client.battle.target.battle.hp = (
                            client.battle.target.battle.maxhp
                        )

                    # send ic healing move
                    if client.battle.target == client:
                        battle_send_ic(
                            client,
                            msg=f"and heals itself of ~{heal}~ hp",
                            effect="lifeup",
                        )
                    else:
                        battle_send_ic(
                            client.battle.target,
                            msg=f"and heals ~{client.battle.target.battle.fighter}~ of ~{heal}~ hp",
                            effect="lifeup",
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
                    damage = move.power + client.battle.atk - target.battle.defe
                    effect = "attack"
                else:
                    damage = move.power + client.battle.spa - target.battle.spd
                    effect = "specialattack"

                # calculate critical damage
                critical = random.randint(1, area.battle_critical_rate)
                critical_message = ""
                if critical == area.battle_critical_rate:
                    critical_message = "with a critical"
                    damage = damage * area.battle_critical_bonus
                target.battle.hp += -damage

                # send ic damage move
                battle_send_ic(
                    target,
                    msg=f"and attacks ~{target.battle.fighter}~ {critical_message} dealing a damage of ~{damage}~",
                    effect=effect,
                    shake=1,
                )

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

                # check if target is dead
                if target.battle.hp <= 0:
                    battle_send_ic(
                        target, msg=f"~{target.battle.fighter}~ ran out of hp!", offset=100
                    )

            #check bonus move effect
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

    # check poisoned fighters 
    for client in area.fighters:
        if client.battle.status == "poison" and client.battle.hp > 0:
            client.battle.hp += -client.battle.maxhp / area.battle_poison_damage
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is affected by poisoning and loses {client.battle.maxhp / area.battle_poison_damage} hp",
                effect="poison",
                shake=1,
            )
            if client.battle.hp <= 0:
                battle_send_ic(
                    client, msg=f"~{client.battle.fighter}~ ran out of hp!", offset=100
                )

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
                client.battle = ClientManager.BattleChar(
                    client, client.battle.fighter, char
                )

    # check if there is a winner or everyone is dead
    if len(area.fighters) == 1:
        winner = area.fighters[0]
        battle_send_ic(winner, msg=f"~{winner.battle.fighter}~ wins the battle!")
        with open(
            f"storage/battlesystem/{winner.battle.fighter}.yaml", "r", encoding="utf-8"
        ) as c_load:
            char = yaml.safe_load(c_load)
            winner.battle = ClientManager.BattleChar(
                winner, winner.battle.fighter, char
            )
    elif len(area.fighters) == 0:
        battle_send_ic(client, msg=f"~Everyone~ is down...", offset=100)
    else:
        # prepare for the next turn
        for client in area.fighters:
            send_stats_fighter(client)
            msg = send_battle_info(client)
            client.send_ooc(msg)
    return area.fighters
