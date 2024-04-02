import yaml

from server.client_manager import ClientManager

from . import mod_only
from .. import commands

__all__ = [
    "ooc_cmd_choose_fighter",
    "ooc_cmd_info_fighter",
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
            client.battle = ClientManager.Battle_char(client, arg)
            send_info_fighter(client)
        else:
            client.send_ooc("No fighter has this name!")


def ooc_cmd_info_fighter(client, arg):
    if client.battle is not None:
        send_info_fighter(client)
    else:
        client.send_ooc("You have to choose a fighter first!")
