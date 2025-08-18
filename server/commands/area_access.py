from server.exceptions import ClientError, ArgumentError, AreaError
from . import mod_only

__all__ = [
    "ooc_cmd_area_lock",
    "ooc_cmd_area_unlock",
    "ooc_cmd_area_mute",
    "ooc_cmd_area_unmute",
    "ooc_cmd_lock",
    "ooc_cmd_unlock",
    "ooc_cmd_pw",
    "ooc_cmd_setpw",
]

@mod_only(area_owners=True)
def ooc_cmd_area_lock(client, arg):
    """
    Prevent users from joining the current area.
    Usage: /area_lock
    """
    args = arg.split()
    if len(args) == 0:
        args = [client.area.id]

    try:
        area_list = []
        for aid in args:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)
            area = client.area.area_manager.get_area_by_id(target_id)

            if not client.is_mod and client not in area.owners:
                if not str(target_id) in client.keys:
                    if area.locking_allowed and area != client.area:
                        client.send_ooc(
                            "You can only lock that area from within!")
                        continue
                    if not area.locking_allowed:
                        client.send_ooc(
                            f"You don't have the keys to {area.name}.")
                        continue
                if not client.can_access_area(area):
                    client.send_ooc(
                        f"You have the keys to {area.name} but it is not accessible from your area."
                    )
                    continue
                if (
                    str(area.id) in client.area.links
                    and client.area.links[str(area.id)]["locked"]
                ):
                    client.send_ooc(
                        f"You have the keys to {area.name} but the path is locked."
                    )
                    continue
            if area.locked:
                client.send_ooc(f"Area {area.name} is already locked.")
                continue
            area.lock()
            area_list.append(area.id)
        if len(area_list) > 0:
            client.send_ooc(f"Locked areas {area_list}.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise


@mod_only(area_owners=True)
def ooc_cmd_area_mute(client, arg):
    """
    Makes this area impossible to speak for normal users unlesss /invite is used.
    Usage: /area_mute
    """
    args = arg.split()
    if len(args) == 0:
        args = [client.area.id]

    try:
        area_list = []
        for aid in args:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)
            area = client.area.area_manager.get_area_by_id(target_id)
            if not client.is_mod and client not in area.owners:
                client.send_ooc(f"You don't own area [{area.id}] {area.name}.")
                continue

            if area.muted:
                client.send_ooc(
                    f"Area [{area.id}] {area.name} is already muted.")
                continue
            area.mute()
            area.broadcast_ooc("This area is now muted.")
            area_list.append(area.id)
        if len(area_list) > 0:
            client.send_ooc(f"Made areas {area_list} muted.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise


@mod_only(area_owners=True)
def ooc_cmd_area_unmute(client, arg):
    """
    Undo the effects of /area_mute.
    Usage: /area_unmute
    """
    args = arg.split()
    if len(args) == 0:
        args = [client.area.id]

    try:
        area_list = []
        for aid in args:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)
            area = client.area.area_manager.get_area_by_id(target_id)
            if not client.is_mod and client not in area.owners:
                client.send_ooc(f"You don't own area [{area.id}] {area.name}.")
                continue

            if not area.muted:
                client.send_ooc(
                    f"Area [{area.id}] {area.name} is already unmuted.")
                continue
            area.unmute()
            area.broadcast_ooc("This area is no longer muted.")
            area_list.append(area.id)
        if len(area_list) > 0:
            client.send_ooc(f"Made areas {area_list} unmuted.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise

@mod_only(area_owners=True)
def ooc_cmd_area_unlock(client, arg):
    """
    Allow anyone to freely join the current area.
    Usage: /area_unlock
    """
    args = arg.split()
    if len(args) == 0:
        args = [client.area.id]

    try:
        area_list = []
        for aid in args:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)
            area = client.area.area_manager.get_area_by_id(target_id)

            if not client.is_mod and client not in area.owners:
                if not str(target_id) in client.keys:
                    if area.locking_allowed and area != client.area:
                        client.send_ooc(
                            "You can only unlock that area from within!")
                        continue
                    if not area.locking_allowed:
                        client.send_ooc(
                            "You don't have the keys to {area.name}.")
                        continue
                if not client.can_access_area(area):
                    client.send_ooc(
                        f"You have the keys to {area.name} but it is not accessible from your area."
                    )
                    continue
                if (
                    str(area.id) in client.area.links
                    and client.area.links[str(area.id)]["locked"]
                ):
                    client.send_ooc(
                        f"You have the keys to {area.name} but the path is locked."
                    )
                    continue
            if not area.locked:
                client.send_ooc(f"Area {area.name} is already unlocked.")
                continue
            area.unlock()
            area_list.append(area.id)
        if len(area_list) > 0:
            client.send_ooc(f"Unlocked areas {area_list}.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise

@mod_only(area_owners=True)
def ooc_cmd_lock(client, arg):
    """
    Context-sensitive function to lock area(s) and/or area link(s).
    Usage: /lock - lock current area. /lock [id] - lock target area. /lock !5 - lock the link from current area to area 5.
    Multiple targets may be passed.
    """
    if arg == "":
        arg = str(client.area.id)
    args = arg.split()
    areas = args.copy()
    links = []
    for a in args:
        if not a.startswith("!"):
            continue
        areas.remove(a)
        links.append(a[1:])
    if len(areas) > 0:
        areas = " ".join(areas)
        ooc_cmd_area_lock(client, areas)
    if len(links) > 0:
        links = " ".join(links)
        print(links)
        ooc_cmd_link_lock(client, links)

@mod_only(area_owners=True)
def ooc_cmd_unlock(client, arg):
    """
    Context-sensitive function to unlock area(s) and/or area link(s).
    Usage: /unlock - unlock current area. /unlock [id] - unlock target area. /unlock !5 - unlock the link from current area to area 5.
    Multiple targets may be passed.
    """
    if arg == "":
        arg = str(client.area.id)
    args = arg.split()
    areas = args.copy()
    links = []
    for a in args:
        if not a.startswith("!"):
            continue
        areas.remove(a)
        links.append(a[1:])
    if len(areas) > 0:
        areas = " ".join(areas)
        ooc_cmd_area_unlock(client, areas)
    if len(links) > 0:
        links = " ".join(links)
        ooc_cmd_link_unlock(client, links)


def ooc_cmd_pw(client, arg):
    """
    Enter a passworded area. Password is case-sensitive and must match the set password exactly, otherwise it will fail.
    You will move into the target area as soon as the correct password is provided.
    Leave password empty if you own the area and want to check its current password.
    Usage:  /pw <id> [password]
    """
    link = None
    password = ""
    if arg == "":
        if not client.is_mod and not (client in client.area.owners):
            raise ArgumentError(
                "You are not allowed to see this area's password. Use /pw <id> [password]"
            )
        aid = client.area.id
    else:
        args = arg.split()
        aid = args[0]
        if aid in client.area.links:
            link = client.area.links[aid]
        if len(args) > 1:
            password = args[1]

    try:
        area = client.area.area_manager.get_area_by_id(int(aid))
        if password == "":
            if client.is_mod or client in client.area.owners:
                if link is not None and link["password"] != "":
                    client.send_ooc(
                        f'Link {client.area.id}-{area.id} password is: {link["password"]}'
                    )
                else:
                    client.send_ooc(
                        f"Area [{area.id}] {area.name} password is: {area.password}"
                    )
            else:
                raise ClientError(
                    "You must provide a password. Use /pw <id> [password]"
                )
        else:
            client.change_area(area, password=password)
    except ValueError:
        raise ArgumentError("Area ID must be a number.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
def ooc_cmd_setpw(client, arg):
    """
    Context-sensitive function to set a password area(s) and/or area link(s).
    Pass area id, or link id from current area using !, e.g. 5 vs !5.
    Leave [password] blank to clear the password.
    Usage:  /setpw <id> [password]
    """
    args = arg.split()
    if len(args) == 0:
        raise ArgumentError(
            "Invalid number of arguments. Use /setpw <id> [password]")

    try:
        password = ""
        link = None
        area = client.area
        if args[0].startswith("!"):
            num = args[0][1:]
            if num in client.area.links:
                link = client.area.links[num]
                area = client.area.area_manager.get_area_by_id(int(num))
            else:
                raise ArgumentError(
                    "Targeted link does not exist in current area.")
        else:
            area = client.area.area_manager.get_area_by_id(int(args[0]))
        if len(args) > 1:
            password = args[1]
        if not client.is_mod and not (client in area.owners):
            raise ClientError("You do not own that area!")
        if link is not None:
            link["password"] = password
            client.send_ooc(
                f"Link {client.area.id}-{area.id} password set to: {password}"
            )
        else:
            area.password = password
            client.send_ooc(
                f"Area [{area.id}] {area.name} password set to: {password}")
    except ValueError:
        raise ArgumentError(
            "Area ID must be a number, or a link ID must start with ! e.g. 5 vs !5."
        )
    except (AreaError, ClientError):
        raise
