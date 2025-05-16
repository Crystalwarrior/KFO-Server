import shlex
import yaml
import os

import re

from server import database
from server.constants import TargetType, derelative
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only

__all__ = [
    "ooc_cmd_inventory",
    "ooc_cmd_inventory_drop",
    "ooc_cmd_inventory_get",
]


def get_inventory(evi_list, arg):
    # Just read all inventory evidence
    if arg == "":
        msg = ""
        for i, evi in enumerate(evi_list):
            # 0 = name
            # 1 = desc
            # 2 = image
            evi_msg = f"\n💼[{i+1}]: '{evi[0]}'"  # (🖼️{evi[2]})
            if arg == "" or arg.lower() in evi_msg.lower():
                msg += evi_msg
        msg += "\n\n|| Use /inventory [evi_name/id] to read specific evidence. ||"
        return msg

    # Arg is not empty
    try:
        evidence = None
        for i, evi in enumerate(evi_list):
            if (arg.isnumeric() and int(arg) - 1 == i) or arg.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(
                f"Target evidence not found! (/inventory {arg})"
            )
        msg = f"==💼[{i+1}]: '{evidence[0]}=="
        msg += f"\n🖼️Image: {evidence[2]}"
        msg += f"\n📃Desc:\n{evidence[1]}"
        msg += f"\n\n|| Use /inventory_drop {i} to drop this into the area ||"
        return msg
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


def ooc_cmd_inventory(client, arg):
    """
    Use /inventory to read all evidence in your inventory.
    Use /inventory [evi_name/id] to read specific evidence.
    Usage: /inventory [evi_name/id]
    """
    msg = f"==Evidence in '{client.char_name}' inventory==\n"
    client.send_ooc(msg + get_inventory(client.inventory, arg))


def ooc_cmd_inventory_drop(client, arg):
    """
    Use /inventory_drop [evi_name/id] to drop evidence from your inventory into the area.
    Usage: /inventory_drop [evi_name/id]
    """
    evi_list = client.inventory

    # Just read all inventory evidence
    if arg == "":
        client.send_ooc("funi")
        return

    # Arg is not empty
    try:
        evidence = None
        for i, evi in enumerate(evi_list):
            if (arg.isnumeric() and int(arg) - 1 == i) or arg.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(
                f"Target evidence not found! (/inventory_drop {arg})"
            )
        client.area.evi_list.add_evidence(
            client, evidence[0], evidence[1], evidence[2]
        )
        client.remove_inventory_evidence(i)
        client.area.broadcast_evidence_list()
        msg = f"You drop '{evidence[0]}' evidence into [{client.id}] {client.area.name}."
        client.send_ooc(msg)
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_inventory_get(client, arg):
    """
    Get someone else's character inventory.
    Usage: /inventory_get <id>
    """
    try:
        if arg.isnumeric():
            target = client.server.client_manager.get_targets(
                client, TargetType.ID, int(arg), False
            )
            if target:
                target = target[0].char_id
            else:
                if arg != "-1" and (int(arg) in client.area.area_manager.char_list):
                    target = int(arg)
        else:
            try:
                target = client.area.area_manager.get_char_id_by_name(arg)
            except (ServerError):
                raise
        
        desc = client.area.area_manager.get_character_data(target, "inventory", "")
        target = client.area.area_manager.char_list[target]
        msg = f"==Evidence in '{target}' inventory==\n"
        client.send_ooc(get_inventory(desc, ""))
        database.log_area(
            "inventory.get", client, client.area, message=f"{target}: {desc}"
        )
    except Exception:
        raise ArgumentError("Target not found.")
