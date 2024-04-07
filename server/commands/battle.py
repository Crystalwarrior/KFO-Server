import yaml
import random

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
    "ooc_cmd_custom_battle",
    "ooc_cmd_fight",
    "ooc_cmd_atk",
    "ooc_cmd_battle_info",
    "ooc_cmd_refresh_battle",
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
    msg = f"\n👤 {client.battle.fighter} 👤:\n\nHP 💗: {client.battle.hp}/{client.battle.maxhp}\nATK 🗡️: {client.battle.atk}\nDEF 🛡️: {client.battle.defe}\nSPA ✨: {client.battle.spa}\nSPD 🔮: {client.battle.spd}\nSPE 💨: {client.battle.spe}\n\n"
    for move in client.battle.moves:
        msg += f"🌠 {move.name} 🌠:\nType 💠: {move.type}\nPower 💪: {move.power}\nAccuracy 🔎: {move.accuracy}%\n Effects 🔰:\n"
        for effect in move.effect:
            msg += f"- {effect}\n"
        msg += "\n"
    client.send_ooc(msg)


def ooc_cmd_choose_fighter(client, arg):
    """
    Allow you to choose a fighter from the list of the server.
    You will receive its stats and its moves.
    Usage: /choose_fighter NameFighter
    """
    with open("storage/battlesystem/battlesystem.yaml", "r", encoding="utf-8") as c:
        char = yaml.safe_load(c)
        if arg.lower() in char:
            client.battle = ClientManager.Battle_char(client, arg.lower())
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
    args = arg.split(" ")
    if len(args) < 8:
        if len(args) > 6:
            if (
                args[1].isdigit()
                and args[2].isdigit()
                and args[3].isdigit()
                and args[4].isdigit()
                and args[5].isdigit()
                and args[6].isdigit()
            ):
                if (
                    float(args[1]) > 0
                    and float(args[2]) > 0
                    and float(args[3]) > 0
                    and float(args[4]) > 0
                    and float(args[5]) > 0
                    and float(args[6]) > 0
                ):
                    with open(
                        "storage/battlesystem/battlesystem.yaml", "r", encoding="utf-8"
                    ) as c_load:
                        char = yaml.safe_load(c_load)
                        args[0] = args[0].lower()
                        if args[0] not in char:
                            char[args[0]] = {}
                            char[args[0]]["HP"] = float(args[1])
                            char[args[0]]["ATK"] = float(args[2])
                            char[args[0]]["DEF"] = float(args[3])
                            char[args[0]]["SPA"] = float(args[4])
                            char[args[0]]["SPD"] = float(args[5])
                            char[args[0]]["SPE"] = float(args[6])
                            char[args[0]]["Moves"] = []
                            with open(
                                "storage/battlesystem/battlesystem.yaml",
                                "w",
                                encoding="utf-8",
                            ) as c_save:
                                yaml.dump(char, c_save)
                                client.send_ooc(f"{args[0]} has been created!")
                        else:
                            client.send_ooc("This fighter has already been created.")
                else:
                    client.send_ooc(
                        "hp, atk, def, spa, spd, spe have to be greater than zero!"
                    )
            else:
                client.send_ooc("Some argument is not an integer.")
        else:
            client.send_ooc("Not enough arguments...")
    else:
        client.send_ooc("Too many arguments...")


def ooc_cmd_create_move(client, arg):
    """
    Allow you to create a move for a fighter.
    You have to choose a fighter first!
    MovesType: Atk or Spa
    Usage: /create_move MoveName MovesType Power Accuracy Effects
    """
    if client.battle is not None:
        args = arg.split(" ")
        if args[2].isdigit and float(args[2]) > 0:
            if args[3].isdigit and float(args[3]) > 0 and float(args[3]) < 101:
                if args[1].lower() in ["atk", "spa"]:
                    with open(
                        "storage/battlesystem/battlesystem.yaml", "r", encoding="utf-8"
                    ) as c_load:
                        char = yaml.safe_load(c_load)
                        fighter = client.battle.fighter
                        move_list = []
                        for i in range(0, len(char[fighter]["Moves"])):
                            move_list.append(char[fighter]["Moves"][i]["Name"])
                        if args[0].lower() not in move_list:
                            char[fighter]["Moves"].append({})
                            index = len(char[fighter]["Moves"]) - 1
                            char[fighter]["Moves"][index]["Name"] = args[0].lower()
                            char[fighter]["Moves"][index]["MovesType"] = args[1].lower()
                            char[fighter]["Moves"][index]["Power"] = float(args[2])
                            char[fighter]["Moves"][index]["Accuracy"] = float(args[3])
                            char[fighter]["Moves"][index]["Effects"] = []
                            for i in range(4, len(args)):
                                if args[i].lower() in battle_effects:
                                    char[fighter]["Moves"][index]["Effects"].append(
                                        args[i].lower()
                                    )
                            with open(
                                "storage/battlesystem/battlesystem.yaml",
                                "w",
                                encoding="utf-8",
                            ) as c_save:
                                yaml.dump(char, c_save)
                                client.battle = ClientManager.Battle_char(
                                    client, fighter
                                )
                                client.send_ooc(f"{args[0]} has been added!")
                        else:
                            client.send_ooc("This move has already been created.")
                else:
                    client.send_ooc("Move's Type should be atk or spa!")
            else:
                client.send_ooc("Accuracy should be a integer between 1 and 100")
        else:
            client.send_ooc("Power argument is not an integer.")
    else:
        client.send_ooc(
            "You have to choose a figher to create a move.\n /choose_fighter FighterName"
        )


@mod_only(hub_owners=True)
def ooc_cmd_modify_stat(client, arg):
    """
    Allow you to modify fighter's stats.
    Usage: /modify_stat FighterName Stat Value
    """
    args = arg.split(" ")
    with open(
        "storage/battlesystem/battlesystem.yaml", "r", encoding="utf-8"
    ) as c_load:
        char = yaml.safe_load(c_load)
        if args[0].lower() in char:
            if args[1].lower() in ["hp", "atk", "def", "spa", "spd", "spe"]:
                if args[2].isdigit and float(args[2]) > 0:
                    char[args[0].lower()][args[1].upper()] = float(args[2])
                    with open(
                        "storage/battlesystem/battlesystem.yaml", "w", encoding="utf-8"
                    ) as c_save:
                        yaml.dump(char, c_save)
                        client.send_ooc(
                            f"{args[0]}'s {args[1]} has been modified. To check the changes choose again this fighter"
                        )
                else:
                    client.send_ooc("The value have to be an integer greater than zero")
            else:
                client.send_ooc(
                    "You could just modify this stats:\nhp, atk, def, spa, spd, spe"
                )
        else:
            client.send_ooc("No fighter has this name!")


@mod_only(hub_owners=True)
def ooc_cmd_delete_fighter(client, arg):
    """
    Allow you to delete a fighter.
    Usage: /delete_move FighterName
    """
    with open(
        "storage/battlesystem/battlesystem.yaml", "r", encoding="utf-8"
    ) as c_load:
        char = yaml.safe_load(c_load)
        if arg.lower() in char:
            char.pop(arg.lower())
            with open(
                "storage/battlesystem/battlesystem.yaml", "w", encoding="utf-8"
            ) as c_save:
                yaml.dump(char, c_save)
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
    if client.battle is not None:
        with open(
            "storage/battlesystem/battlesystem.yaml", "r", encoding="utf-8"
        ) as c_load:
            char = yaml.safe_load(c_load)
            move_list = []
            for i in range(0, len(char[client.battle.fighter]["Moves"])):
                move_list.append(char[client.battle.fighter]["Moves"][i]["Name"])
            if arg.lower() in move_list:
                index = move_list.index(arg.lower())
                char[client.battle.fighter]["Moves"].pop(index)
                with open(
                    "storage/battlesystem/battlesystem.yaml", "w", encoding="utf-8"
                ) as c_save:
                    yaml.dump(char, c_save)
                    client.battle = ClientManager.Battle_char(
                        client, client.battle.fighter
                    )
                    client.send_ooc(f"{arg} has been deleted!")
            else:
                client.send_ooc(f"{arg} is not found in the fighter moves")
    else:
        client.send_ooc("You have to choose the fighter first")


@mod_only(hub_owners=True)
def ooc_cmd_custom_battle(client, arg):
    """
    Allow you to customize some battle settings.
    parameters: paralysis_rate, critical_rate, critical_bonus, bonus_malus, poison_damage
    Usage: /custom_battle parameter value
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
    else:
        client.send_ooc("value is not a digit")


def send_battle_info(client):
    msg = "\n⚔️🛡️ Battle Fighters Info 🛡️⚔️:\n\n"
    for client in client.area.fighters:
        if client.battle.selected_move == -1:
            emoji = "🔎"
        else:
            emoji = "⚔️"
        msg += (
            f"{emoji} [{client.id}]{client.battle.fighter} ({client.showname}) {emoji}\n"
        )
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
    if client.area.can_battle:
        if client.battle is not None:
            if client not in client.area.fighters:
                if not client.area.battle_started:
                    client.area.fighters.append(client)
                    msg = send_battle_info(client)
                    for client in client.area.fighters:
                        client.send_ooc(msg)
                    client.area.broadcast_ooc(
                        f"⚔️{client.battle.fighter} ({client.showname}) is ready to fight!⚔️"
                    )
                    fighter_name = client.area.area_manager.char_list[client.char_id]
                    client.area.send_ic(
                        client=None,
                        msg_type="1",
                        pre=client.last_sprite,
                        folder=fighter_name,
                        anim=client.last_sprite,
                        msg=f"~{client.battle.fighter}~ is ready to fight",
                        pos=client.pos,
                        sfx="",
                        emote_mod=0,
                        cid=-1,
                        sfx_delay=0,
                        button=0,
                        evidence=[0],
                        flip=client.flip,
                        ding=0,
                        color=3,
                        showname="",
                        charid_pair=client.charid_pair,
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
                    )
                else:
                    client.send_ooc("The battle is already started!")
            else:
                client.send_ooc("You are already in battle!")
        else:
            client.send_ooc("You have to choose a fighter to start a battle!")
    else:
        client.send_ooc("You cannot fight in this area!")


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


def ooc_cmd_atk(client, arg):
    """
    This command will let you use a move during a battle!
    Heal and AttAll moves don't need a target!
    Usage: /atk MoveName Target_ID
    """
    if client.battle is not None:
        if client in client.area.fighters:
            if client.battle.selected_move == -1:
                args = arg.split(" ")
                moves_list = [move.name for move in client.battle.moves]
                if args[0].lower() in moves_list:
                    move_id = moves_list.index(args[0].lower())
                    if len(args) == 2:
                        fighter_id_list = {c.id: c for c in client.area.fighters}
                        if int(args[1]) in fighter_id_list:
                            client.battle.target = fighter_id_list[int(args[1])]
                            client.battle.selected_move = move_id
                            client.area.num_selected_move += 1
                            client.send_ooc(f"You have choosen {args[0].lower()}")
                        else:
                            client.send_ooc("Your target is not in the fighter list")
                    elif "heal" in client.battle.moves[move_id]["Effects"]:
                        client.battle.target = client
                        client.battle.selected_move = move_id
                        client.area.num_selected_move += 1
                        client.send_ooc(f"You have choosen {args[0].lower()}")
                    elif "atkall" in client.battle.moves[move_id]["Effects"]:
                        client.battle.target = "all"
                        client.battle.selected_move = move_id
                        client.area.num_selected_move += 1
                        client.send_ooc(f"You have choosen {args[0].lower()}")
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
                else:
                    client.send_ooc("There is no move with this name!")
            else:
                client.send_ooc("You already selected a move!")
        else:
            client.send_ooc("You are not ready to fight!")
    else:
        client.send_ooc("You have to choose a fighter first!")


def start_battle_animation(area):
    # first of all we sort the fighters compared to their speed.
    fighter_speed = {client: client.battle.spe for client in area.fighters}
    sorted_fighter_speed = sorted(fighter_speed.items(), key=lambda x: x[1])
    sorted_fighter_speed = dict(sorted_fighter_speed)
    area.fighters = list(sorted_fighter_speed.keys())
    for client in list(area.fighters):
        if client.battle.hp > 0:    
            fighter_name = client.area.area_manager.char_list[client.char_id]
            move = client.battle.moves[client.battle.selected_move]
            # check if the fighter misses the move
            miss = random.randint(0, 99)
            if move.accuracy > miss:
                # check if the fighter is paralysed
                paralysis = random.randint(1, area.battle_paralysis_rate)
                if paralysis < area.battle_paralysis_rate or client.battle.status != "paralysis":
                    if "heal" in move.effect or "healally" in move.effect:
                        targets = []
                    elif "atkall" in move.effect:
                        targets = area.fighters
                        targets.remove(client)
                    else:
                        if client.battle.target in area.fighters:
                            targets = [client.battle.target]
                        else:
                            targets = []
                    #send in ic the message 'fighter uses this move'
                    area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"~{client.battle.fighter}~ uses ~{move.name}~", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)
                    if targets == []:
                        if "heal" in move.effect or "healally" in move.effect:
                            if client.battle.target in area.fighter:
                                if "atk" == move.type:
                                    heal = (move.power + client.battle.atk) * 0.25
                                else:
                                    heal = (move.power + client.battle.spa) * 0.25   
                                client.battle.target.battle.hp += heal
                                if client.battle.target.battle.hp > client.battle.target.battle.maxhp:
                                    client.battle.target.battle.hp = client.battle.target.battle.maxhp
                                if client.battle.target == client:
                                    area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"and heals itself of ~{heal}~ hp", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="lifeup", targets=None)
                                else:
                                    target_fighter_name = client.battle.target.area.area_manager.char_list[client.battle.target.char_id]
                                    area.send_ic(client=None, msg_type="1", pre=client.battle.target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"and heals ~{client.battle.target.battle.fighter}~ of ~{heal}~ hp", pos=client.battle.target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.battle.target.flip, ding=0, color=3, showname="", charid_pair=client.battle.target.charid_pair, other_folder="", other_emote="", offset_pair=client.battle.target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="lifeup", targets=None)
                            else:
                                area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"and tries to heal but the target is already dead", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)      
                        else:
                            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"and tries to attack but the target is already dead", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)
                    else:
                        for target in targets:
                            target_fighter_name = target.area.area_manager.char_list[target.char_id]
                            #calculate damage
                            if move.type == "atk":
                                damage = (
                                    move.power * client.battle.atk / 5 * target.battle.defe
                                )
                                effect = "attack"
                            else:
                                damage = (
                                    move.power * client.battle.spa / 5 * target.battle.spd
                                )
                                effect = "specialattack"
                            #calculate critical damage
                            critical = random.randint(1,area.battle_critical_rate)
                            critical_message = ""
                            if critical == 1:
                                critical_message = "with a critical"
                                damage = damage*area.battle_critical_bonus
                            target.battle.hp += -damage
                            area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"and attacks ~{target.battle.fighter}~ {critical_message} dealing a damage of ~{damage}~", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=1, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect=effect, targets=None)
                            if "atkdown" in move.effect:
                                target.battle.atk = target.battle.atk / area.battle_bonus_malus
                                area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"The attack of ~{target.battle.fighter}~ goes down", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statdown", targets=None)
                            if "defdown" in move.effect:
                                target.battle.defe = target.battle.defe / area.battle_bonus_malus
                                area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"The defense of ~{target.battle.fighter}~ goes down", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statdown", targets=None)
                            if "spadown" in move.effect:
                                target.battle.spa = target.battle.spa / area.battle_bonus_malus
                                area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"The special attack of ~{target.battle.fighter}~ goes down", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statdown", targets=None)
                            if "spddown" in move.effect:
                                target.battle.spd = target.battle.spd / area.battle_bonus_malus
                                area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"The special defense of ~{target.battle.fighter}~ goes down", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statdown", targets=None)
                            if "spedown" in move.effect:
                                target.battle.spe = target.battle.spe / area.battle_bonus_malus
                                area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"The speed of ~{target.battle.fighter}~ goes down", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statdown", targets=None)
                            if "poison" in move.effect:
                                if target.battle.status is None:
                                    target.battle.status = "poison"
                                    area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"~{target.battle.fighter}~ is affected by poisoning", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="poison", targets=None)
                            if "paralysis" in move.effect:
                                if target.battle.status is None:
                                    target.battle.status = "paralysis"
                                    area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"~{target.battle.fighter}~ is affected by paralysis", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=target.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=1, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="paralysis", targets=None)
                            if target.battle.hp < 1:
                                target.battle.selected_move = -1
                                target.battle.target = None
                                area.fighters.remove(target)
                                target.battle = ClientManager.Battle_char(
                                    target, target.battle.fighter
                                )
                                area.send_ic(client=None, msg_type="1", pre=target.last_sprite, folder=target_fighter_name, anim=client.last_sprite, msg=f"~{target.battle.fighter}~ dies...", pos=target.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=target.flip, ding=0, color=3, showname="", charid_pair=target.charid_pair, other_folder="", other_emote="", offset_pair=100, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)
                        if "atkraise" in move.effect:
                            client.battle.atk = client.battle.atk * area.battle_bonus_malus
                            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"The attack goes up", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statup", targets=None)
                        if "defraise" in move.effect:
                            client.battle.defe = client.battle.defe * area.battle_bonus_malus
                            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"The defense goes up", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statup", targets=None)
                        if "sparaise" in move.effect:
                            client.battle.spa = client.battle.spa * area.battle_bonus_malus
                            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"The special attack goes up", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statup", targets=None)
                        if "spdraise" in move.effect:
                            client.battle.spd = client.battle.spd * area.battle_bonus_malus
                            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"The special defense goes up", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statup", targets=None)
                        if "speraise" in move.effect:
                            client.battle.spe = client.battle.spe * area.battle_bonus_malus
                            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"The speed goes up", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="statup", targets=None)
                else:
                    area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"~{client.battle.fighter}~ is affected by paralysis and cannot fight", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="paralysis", targets=None)  
            else:
                area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"~{client.battle.fighter}~ misses the target", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)  
            client.battle.selected_move = -1
            client.battle.target = None
    for client in list(area.fighters):
        fighter_name = client.area.area_manager.char_list[client.char_id]
        if client.battle.status == "poison":
            client.battle.hp += -client.battle.maxhp / area.battle_poison_damage
            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"~{client.battle.fighter}~ is affected by poisoning and loses {client.battle.maxhp / area.battle_poison_damage} hp", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=client.offset_pair, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="poison", targets=None)
        if client.battle.hp < 1:
            area.fighters.remove(client)
            client.battle = ClientManager.Battle_char(client, client.battle.fighter)
            area.send_ic(client=None, msg_type="1", pre=client.last_sprite, folder=fighter_name, anim=client.last_sprite, msg=f"~{client.battle.fighter}~ dies...", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=100, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)
        send_info_fighter(client)
        msg = send_battle_info(client)
        client.send_ooc(msg)
    if len(area.fighters) == 1:
        winner = area.fighters[0]
        fighter_name = winner.area.area_manager.char_list[winner.char_id]
        area.send_ic(client=None, msg_type="1", pre=1, folder=fighter_name, anim=client.last_sprite, msg=f"~{client.battle.fighter}~ wins the battle!", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=0, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)
        winner.battle = ClientManager.Battle_char(winner, winner.battle.fighter)
    if len(area.fighters) == 0:
        area.send_ic(client=None, msg_type="1", pre=1, folder=fighter_name, anim=client.last_sprite, msg=f"~Everyone~ died...", pos=client.pos, sfx="", emote_mod=0, cid=-1, sfx_delay=0, button=0, evidence=[0], flip=client.flip, ding=0, color=3, showname="", charid_pair=client.charid_pair, other_folder="", other_emote="", offset_pair=0, other_offset=0, other_flip=0, nonint_pre=0, sfx_looping="0", screenshake=0, frames_shake="", frames_realization="", frames_sfx="", additive=0, effect="", targets=None)
    return area.fighters
