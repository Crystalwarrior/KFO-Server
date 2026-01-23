import shlex


from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only

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
            evi_msg = f"\n💼[{i + 1}]: '{evi[0]}'"  # (🖼️{evi[2]})
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
            raise AreaError(f"Target evidence not found! (/inventory {arg})")
        msg = f"==💼[{i + 1}]: '{evidence[0]}=="
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
            raise AreaError(f"Target evidence not found! (/inventory_drop {arg})")
        client.area.evi_list.add_evidence(client, evidence[0], evidence[1], evidence[2])
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
        target = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
        if target:
            target = target[0].char_id
        else:
            if arg != "-1" and (int(arg) in client.area.area_manager.char_list):
                target = int(arg)
    else:
        try:
            target = client.area.area_manager.get_char_id_by_name(arg)
        except ServerError:
            raise
    return target


@mod_only(hub_owners=True)
def ooc_cmd_inventory_get(client, arg):
    """
    Get someone else's character inventory.
    Usage: /inventory_get <id>
    """
    try:
        # Get the user input
        args = shlex.split(arg)

        target = get_inventory_target(client, args.pop(0))

        inventory = client.area.area_manager.get_character_data(target, "inventory", "")
        charname = client.area.area_manager.char_list[target]
        inventory_list = get_inventory(inventory, " ".join(args))
        msg = f"==Evidence in '{charname}' inventory==\n{inventory_list}"
        client.send_ooc(msg)
        database.log_area("inventory.get", client, client.area, message=charname)
    except ValueError as ex:
        client.send_ooc(f"{ex} (/inventory_get {arg})")
        return


@mod_only(hub_owners=True)
def ooc_cmd_inventory_add(client, arg):
    """
    Use /inventory <target> [evi_name/id] to add evidence into their inventory.
    Usage: /inventory_add <target> [evi_name/id]
    """
    try:
        # Get the user input
        args = shlex.split(arg)

        target = get_inventory_target(client, args.pop(0))

        max_args = 3
        if len(args) > max_args:
            raise ArgumentError(
                f"Too many arguments! Make sure to surround your args in \"\"'s if there's spaces. (/inventory_add {arg})"
            )
        # fill the rest of it with asterisk to fill to max_args
        args = args + ([""] * (max_args - len(args)))
        if args[0] == "":
            args[0] = "<name>"
        if args[1] == "":
            args[1] = "<description>"
        if args[2] == "":
            args[2] = "empty.png"
    except ValueError as ex:
        client.send_ooc(f"{ex} (/inventory_add {arg})")
        return

    inventory = client.area.area_manager.get_character_data(target, "inventory", list())
    inventory.append([args[0], args[1], args[2]])
    client.area.area_manager.set_character_data(target, "inventory", inventory)
    charname = client.area.area_manager.char_list[target]
    client.send_ooc(f"Added evidence '{args[0]}' into {charname}'s inventory")


@mod_only(hub_owners=True)
def ooc_cmd_inventory_remove(client, arg):
    """
    Remove a piece of evidence from target's inventory.
    Usage: /inventory_remove <target> <evi_name/id>
    """
    try:
        args = shlex.split(arg)
        target = get_inventory_target(client, args.pop(0))
        if len(args) > 1:
            raise ArgumentError(
                f"Too many arguments! Make sure to surround your args in \"\"'s if there's spaces. (/inventory_remove {arg})"
            )

        inventory = client.area.area_manager.get_character_data(target, "inventory", list())

        arg = " ".join(args)
        evidence = None
        for i, evi in enumerate(inventory):
            if (arg.isnumeric() and int(arg) - 1 == i) or arg.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(f"Target evidence not found! (/inventory_remove {arg})")
        inventory.pop(i)
        client.area.area_manager.set_character_data(target, "inventory", inventory)
    except ValueError as ex:
        client.send_ooc(f"{ex} (/inventory_remove {arg})")
        return


@mod_only(hub_owners=True)
def ooc_cmd_inventory_edit(client, arg):
    """
    Edit a piece of evidence in target's inventory.
    If you don't want to change something, put an * there.
    For sentences with spaces the arg should be surrounded in ""'s, for example /inventory_edit * "It's a chair." chair.png
    Usage: /inventory_edit <target> <evi_name/id> [name] [desc] [image]
    """
    if arg == "":
        raise ArgumentError(
            "Use /inventory_edit <target> <evi_name/id> [name] [desc] [image] to edit that piece of evidence."
        )

    try:
        # Get the user input
        args = shlex.split(arg)
        target = get_inventory_target(client, args.pop(0))
        target_evi = args.pop(0)

        max_args = 3
        if len(args) > max_args:
            raise ArgumentError(
                f"Too many arguments! Make sure to surround your args in \"\"'s if there's spaces. (/inventory_edit {arg})"
            )
        # fill the rest of it with asterisk to fill to max_args
        args = args + (["*"] * (max_args - len(args)))
    except ValueError as ex:
        client.send_ooc(f"{ex} (/inventory_edit {arg})")
        return

    try:
        inventory = client.area.area_manager.get_character_data(target, "inventory", list())
        evidence = None
        for i, evi in enumerate(inventory):
            if (target_evi.isnumeric() and int(target_evi) - 1 == i) or target_evi.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(f"Target evidence not found! (/inventory_edit {arg})")
        evi_name = evidence[0]
        inventory[i] = [args[0], args[1], args[2]]
        client.area.area_manager.set_character_data(target, "inventory", inventory)
        database.log_area("inventory.edit", client, client.area)
        charname = client.area.area_manager.char_list[target]
        if args[0] != "*" and target_evi != args[0]:
            client.send_ooc(f"You have edited evidence '{evi_name}' to '{args[0]}' in {charname}'s inventory.")
        else:
            client.send_ooc(f"You have edited evidence '{evi_name}' in {charname}'s inventory.")
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise
