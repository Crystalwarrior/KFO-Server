import yaml

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
        if args[2].isdigit:
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
                if args[2].isdigit:
                    char[args[0].lower()][args[1].upper()] = float(args[2])
                    with open(
                        "storage/battlesystem/battlesystem.yaml", "w", encoding="utf-8"
                    ) as c_save:
                        yaml.dump(char, c_save)
                        client.send_ooc(
                            f"{args[0]}'s stat has been modified. To check the changes choose again this fighter"
                        )
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
