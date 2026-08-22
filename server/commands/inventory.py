import yaml
import os

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only, command, Arg, tokens_str

__all__ = [
    "ooc_cmd_inventory",
    "ooc_cmd_inventory_drop",
    "ooc_cmd_inventory_get",
    "ooc_cmd_inventory_add",
    "ooc_cmd_inventory_remove",
    "ooc_cmd_inventory_edit",
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
        msg = f"==💼[{i+1}]: '{evidence[0]}== "
        msg += f"\n🖼️Image: {evidence[2]}"
        msg += f"\n📃Desc:\n{evidence[1]}"
        msg += f"\n\n|| Use /inventory_drop {i} to drop this into the area ||"
        return msg
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


@command(Arg("arg", rest=True, default="", help="evidence name or id"))
def ooc_cmd_inventory(client, arg):
    """
    Use /inventory to read all evidence in your inventory.
    Use /inventory [evi_name/id] to read specific evidence.
    Usage: /inventory [evi_name/id]
    """
    msg = f"==Evidence in '{client.char_name}' inventory==\n"
    client.send_ooc(msg + get_inventory(client.inventory, arg))


@command(Arg("arg", rest=True, default="", help="evidence name or id"))
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


def get_inventory_target(client, arg):
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
    return target


@mod_only(hub_owners=True)
@command(
    Arg("target", help="character id, folder or name"),
    Arg("name", rest=True, default="", type=tokens_str, help="evidence name or id"),
)
def ooc_cmd_inventory_get(client, target, name):
    """
    Get someone else's character inventory.
    Usage: /inventory_get <id>
    """
    target = get_inventory_target(client, target)

    inventory = client.area.area_manager.get_character_data(target, "inventory", "")
    charname = client.area.area_manager.char_list[target]
    inventory_list = get_inventory(inventory, name)
    msg = f"==Evidence in '{charname}' inventory==\n{inventory_list}"
    client.send_ooc(msg)
    database.log_area(
        "inventory.get", client, client.area, message=charname
    )


@mod_only(hub_owners=True)
@command(
    Arg("target", help="character id, folder or name"),
    Arg("name", default="<name>", help="evidence name"),
    Arg("description", default="<description>", help="evidence description"),
    Arg("image", default="empty.png", help="evidence image"),
)
def ooc_cmd_inventory_add(client, target, name, description, image):
    """
    Use /inventory_add <target> [name] [description] [image] to create a new piece of evidence from scratch,
    adding it  into their inventory.
    Usage: /inventory_add <target> [name] [description] [image]
    """
    target = get_inventory_target(client, target)

    inventory = client.area.area_manager.get_character_data(target, "inventory", list())
    inventory.append([name, description, image])
    client.area.area_manager.set_character_data(target, "inventory", inventory)
    charname = client.area.area_manager.char_list[target]
    client.send_ooc(f"Added evidence '{name}' into {charname}'s inventory")


@mod_only(hub_owners=True)
@command(
    Arg("target", help="character id, folder or name"),
    Arg("name", rest=True, default="", type=tokens_str, help="evidence name or id"),
)
def ooc_cmd_inventory_remove(client, target, name):
    """
    Remove a piece of evidence from target's inventory.
    Usage: /inventory_remove <target_id> <evi_name/id>
    """
    target = get_inventory_target(client, target)

    inventory = client.area.area_manager.get_character_data(target, "inventory", list())

    evidence = None
    for i, evi in enumerate(inventory):
        if (name.isnumeric() and int(name) - 1 == i) or name.lower() == evi[0].lower():
            evidence = evi
            break
    if evidence is None:
        raise AreaError(
            f"Target evidence not found! (/inventory_remove {name})"
        )
    inventory.pop(i)
    client.area.area_manager.set_character_data(target, "inventory", inventory)


@mod_only(hub_owners=True)
@command(
    Arg("target", help="character id, folder or name"),
    Arg("target_evi", help="evidence name or id"),
    Arg("name", default="*", help="new evidence name"),
    Arg("description", default="*", help="new evidence description"),
    Arg("image", default="*", help="new evidence image"),
)
def ooc_cmd_inventory_edit(client, target, target_evi, name, description, image):
    """
    Edit a piece of evidence in target's inventory.
    If you don't want to change something, put an * there.
    For sentences with spaces the arg should be surrounded in ""'s, for example /inventory_edit * "It's a chair." chair.png
    Usage: /inventory_edit <target_id> <evi_name/id> [name] [desc] [image]
    """
    target = get_inventory_target(client, target)

    try:
        inventory = client.area.area_manager.get_character_data(target, "inventory", list())
        evidence = None
        for i, evi in enumerate(inventory):
            if (target_evi.isnumeric() and int(target_evi) - 1 == i) or target_evi.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(
                f"Target evidence not found! (/inventory_edit {target_evi})"
            )
        evi_name = evidence[0]
        inventory[i] = [name, description, image]
        client.area.area_manager.set_character_data(target, "inventory", inventory)
        database.log_area("inventory.edit", client, client.area)
        charname = client.area.area_manager.char_list[target]
        if name != "*" and target_evi != name:
            client.send_ooc(
                f"You have edited evidence '{evi_name}' to '{name}' in {charname}'s inventory."
            )
        else:
            client.send_ooc(f"You have edited evidence '{evi_name}' in {charname}'s inventory.")
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise
