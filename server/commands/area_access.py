from server.exceptions import ClientError, ArgumentError, AreaError
from . import mod_only, command, Arg, tokens_str

__all__ = [
    "ooc_cmd_area_lock",
    "ooc_cmd_area_unlock",
    "ooc_cmd_area_mute",
    "ooc_cmd_area_unmute",
    "ooc_cmd_lock",
    "ooc_cmd_unlock",
    "ooc_cmd_link",
    "ooc_cmd_unlink",
    "ooc_cmd_links",
    "ooc_cmd_onelink",
    "ooc_cmd_oneunlink",
    "ooc_cmd_link_lock",
    "ooc_cmd_link_unlock",
    "ooc_cmd_link_hide",
    "ooc_cmd_link_unhide",
    "ooc_cmd_link_pos",
    "ooc_cmd_link_peekable",
    "ooc_cmd_link_unpeekable",
    "ooc_cmd_link_seethrough",
    "ooc_cmd_link_unseethrough",
    "ooc_cmd_link_evidence",
    "ooc_cmd_unlink_evidence",
    "ooc_cmd_pw",
    "ooc_cmd_setpw",
]


@command(Arg("areas", variadic=True, default=None, help="area IDs (blank = current)"))
def ooc_cmd_area_lock(client, areas):
    """
    Prevent users from joining the current area.
    Usage: /area_lock
    """
    if not areas:
        areas = [str(client.area.id)]

    try:
        area_list = client.area.area_manager.get_areas_by_args(areas)
        for area in area_list:
            if not client.is_mod and client not in area.owners:
                if not str(area.id) in client.keys:
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
        if len(area_list) > 0:
            client.send_ooc(f"Locked {len(area_list)} areas.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, default=None, help="area IDs (blank = current)"))
def ooc_cmd_area_mute(client, areas):
    """
    Makes this area impossible to speak for normal users unlesss /invite is used.
    Usage: /area_mute
    """
    if not areas:
        areas = [str(client.area.id)]

    try:
        area_list = client.area.area_manager.get_areas_by_args(areas)
        for area in area_list:
            if not client.is_mod and client not in area.owners:
                client.send_ooc(f"You don't own area [{area.id}] {area.name}.")
                continue

            if area.muted:
                client.send_ooc(
                    f"Area [{area.id}] {area.name} is already muted.")
                continue
            area.mute()
            area.broadcast_ooc("This area is now muted.")
        if len(area_list) > 0:
            client.send_ooc(f"Made {len(area_list)} areas muted.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, default=None, help="area IDs (blank = current)"))
def ooc_cmd_area_unmute(client, areas):
    """
    Undo the effects of /area_mute.
    Usage: /area_unmute
    """
    if not areas:
        areas = [str(client.area.id)]

    try:
        area_list = client.area.area_manager.get_areas_by_args(areas)
        for area in area_list:
            if not client.is_mod and client not in area.owners:
                client.send_ooc(f"You don't own area [{area.id}] {area.name}.")
                continue

            if not area.muted:
                client.send_ooc(
                    f"Area [{area.id}] {area.name} is already unmuted.")
                continue
            area.unmute()
            area.broadcast_ooc("This area is no longer muted.")
        if len(area_list) > 0:
            client.send_ooc(f"Made {len(area_list)} areas unmuted.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise


@command(Arg("areas", variadic=True, default=None, help="area IDs (blank = current)"))
def ooc_cmd_area_unlock(client, areas):
    """
    Allow anyone to freely join the current area.
    Usage: /area_unlock
    """
    if not areas:
        areas = [str(client.area.id)]

    try:
        area_list = client.area.area_manager.get_areas_by_args(areas)
        for area in area_list:
            if not client.is_mod and client not in area.owners:
                if not str(area.id) in client.keys:
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
        if len(area_list) > 0:
            client.send_ooc(f"Unlocked {len(area_list)} areas.")
    except ValueError:
        raise ArgumentError("Target must be an abbreviation or number.")
    except (ClientError, AreaError):
        raise


@command(Arg("targets", rest=True, type=tokens_str, default="", help="area IDs and/or !link IDs"))
def ooc_cmd_lock(client, targets):
    """
    Context-sensitive function to lock area(s) and/or area link(s).
    Usage: /lock - lock current area. /lock [id] - lock target area. /lock !5 - lock the link from current area to area 5.
    Multiple targets may be passed.
    """
    if targets == "":
        targets = str(client.area.id)
    args = targets.split()
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


@command(Arg("targets", rest=True, type=tokens_str, default="", help="area IDs and/or !link IDs"))
def ooc_cmd_unlock(client, targets):
    """
    Context-sensitive function to unlock area(s) and/or area link(s).
    Usage: /unlock - unlock current area. /unlock [id] - unlock target area. /unlock !5 - unlock the link from current area to area 5.
    Multiple targets may be passed.
    """
    if targets == "":
        targets = str(client.area.id)
    args = targets.split()
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


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, default=None, help="area IDs (blank shows links)"))
def ooc_cmd_link(client, areas):
    """
    Set up a two-way link from your current area with targeted area(s).
    Usage:  /link <id(s)>
    """
    if not areas:
        ooc_cmd_links(client, "")
        return
    try:
        links = []
        for aid in areas:
            try:
                area = client.area.area_manager.get_area_by_abbreviation(aid)
                target_id = area.id
            except Exception:
                area = client.area.area_manager.get_area_by_id(int(aid))
                target_id = area.id

            if not client.is_mod and client not in area.owners:
                client.send_ooc(f"You don't own area [{area.id}] {area.name}.")
                continue

            client.area.link(target_id)
            # Connect the target area to us
            area.link(client.area.id)
            links.append(target_id)
        links = ", ".join(str(link) for link in links)
        client.send_ooc(
            f"Area {client.area.name} has been linked with {links} (two-way)."
        )
        client.area.broadcast_area_list()
        area.broadcast_area_list()
    except ValueError:
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_unlink(client, areas):
    """
    Remove a two-way link from your current area with targeted area(s).
    Usage:  /unlink <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                area = client.area.area_manager.get_area_by_abbreviation(aid)
                target_id = area.id
            except Exception:
                area = client.area.area_manager.get_area_by_id(int(aid))
                target_id = area.id

            if not client.is_mod and client not in area.owners:
                client.send_ooc(f"You don't own area [{area.id}] {area.name}.")
                continue

            try:
                client.area.unlink(target_id)
                # Disconnect the target area from us
                area.unlink(client.area.id)
                links.append(target_id)
            except Exception:
                continue
        links = ", ".join(str(link) for link in links)
        client.send_ooc(
            f"Area {client.area.name} has been unlinked with {links} (two-way)."
        )
        client.area.broadcast_area_list()
        area.broadcast_area_list()
    except ValueError:
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@command()
def ooc_cmd_links(client):
    """
    Display this area's information about area links.
    Usage:  /links
    """
    links = ""
    for key, value in sorted(client.area.links.items(), key=lambda x: int(x[0])):
        hidden = ""
        if value["hidden"] is True:
            # Can't see hidden links
            if not client.is_mod and client not in client.area.owners:
                continue
            hidden = "📦"

        if len(value["evidence"]) > 0 and not (client.hidden_in in value["evidence"]):
            # Can't see hidden links
            if not client.is_mod and client not in client.area.owners:
                continue
            evi_list = ", ".join(str(evi + 1) for evi in value["evidence"])
            hidden = f"📦:{evi_list}"

        try:
            area_name = f' - "{client.area.area_manager.get_area_by_id(int(key)).name}"'
        except Exception:
            area_name = ""

        locked = ""
        if value["locked"] is True:
            locked = "🚧"
        if value["password"] != "":
            locked = "🔑"

        seethrough = ""
        if value.get("seethrough", False) is True:
            seethrough = "👁️"

        target_pos = value["target_pos"]
        if target_pos != "":
            target_pos = f", pos: {target_pos}"
        links += f"\n!{key}{area_name}{locked}{hidden}{seethrough}{target_pos}"

    client.send_ooc(f"Current area links are: {links}")


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, default=None, help="area IDs (blank shows links)"))
def ooc_cmd_onelink(client, areas):
    """
    Set up a one-way link from your current area with targeted area(s).
    Usage:  /onelink <id(s)>
    """
    if not areas:
        ooc_cmd_links(client, "")
        return
    try:
        links = []
        for aid in areas:
            try:
                area = client.area.area_manager.get_area_by_abbreviation(aid)
                target_id = area.id
            except Exception:
                area = client.area.area_manager.get_area_by_id(int(aid))
                target_id = area.id

            if not client.is_mod and client not in area.owners:
                client.send_ooc(f"You don't own area [{area.id}] {area.name}.")
                continue

            client.area.link(target_id)
            links.append(target_id)
        links = ", ".join(str(link) for link in links)
        client.send_ooc(
            f"Area {client.area.name} has been linked with {links} (one-way)."
        )
        client.area.broadcast_area_list()
    except ValueError:
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_oneunlink(client, areas):
    """
    Remove a one-way link from your current area with targeted area(s).
    Usage:  /oneunlink <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)

            try:
                client.area.unlink(target_id)
                links.append(target_id)
            except Exception:
                continue
        links = ", ".join(str(link) for link in links)
        client.send_ooc(
            f"Area {client.area.name} has been unlinked with {links} (one-way)."
        )
        client.area.broadcast_area_list()
    except ValueError:
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_lock(client, areas):
    """
    Lock the path leading to target area(s).
    Usage:  /link_lock <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)
            if not client.is_mod and client not in client.area.owners:
                if f"{client.area.id}-{target_id}" not in client.keys:
                    client.send_ooc(
                        f"You don't have the keys to the link {client.area.id}-{target_id}."
                    )
                    continue
                target_area = client.area.area_manager.get_area_by_id(
                    target_id)
                if (
                    f"{target_id}-{client.area.id}" in client.keys
                    and str(client.area.id) in target_area.links
                ):  # Treat it as a single door/path if we have the keys both ways
                    target_area.links[str(client.area.id)]["locked"] = True
                    client.send_ooc(
                        f"Locked {client.area.id}-{target_id} both ways.")
            client.area.links[str(target_id)]["locked"] = True
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(f"Area {client.area.name} links {links} locked.")
    except (ValueError, KeyError):
        raise ArgumentError(
            "Area ID must be a number or abbreviation and the link must exist."
        )
    except (AreaError, ClientError):
        raise


@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_unlock(client, areas):
    """
    Unlock the path leading to target area(s).
    Usage:  /link_unlock <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)
            if not client.is_mod and client not in client.area.owners:
                if f"{client.area.id}-{target_id}" not in client.keys:
                    client.send_ooc(
                        f"You don't have the keys to the link {client.area.id}-{target_id}."
                    )
                    continue
                target_area = client.area.area_manager.get_area_by_id(
                    target_id)
                if (
                    f"{target_id}-{client.area.id}" in client.keys
                    and str(client.area.id) in target_area.links
                ):  # Treat it as a single door/path if we have the keys both ways
                    target_area.links[str(client.area.id)]["locked"] = False
                    client.send_ooc(
                        f"Unlocked {client.area.id}-{target_id} both ways.")
            client.area.links[str(target_id)]["locked"] = False
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(f"Area {client.area.name} links {links} unlocked.")
    except (ValueError, KeyError):
        raise ArgumentError(
            "Area ID must be a number or abbreviation and the link must exist."
        )
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_hide(client, areas):
    """
    Hide the path leading to target area(s).
    Usage:  /link_hide <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)

            client.area.links[str(target_id)]["hidden"] = True
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(f"Area {client.area.name} links {links} hidden.")
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_unhide(client, areas):
    """
    Unhide the path leading to target area(s).
    Usage:  /link_unhide <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)

            client.area.links[str(target_id)]["hidden"] = False
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(f"Area {client.area.name} links {links} revealed.")
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(
    Arg("id", help="area ID or abbreviation"),
    Arg("pos", rest=True, type=tokens_str, default="", help="target pos (blank resets)"),
)
def ooc_cmd_link_pos(client, id, pos):
    """
    Set the link's targeted pos when using it. Leave blank to reset.
    Usage:  /link_pos <id> [pos]
    """
    try:
        try:
            target_id = client.area.area_manager.get_area_by_abbreviation(
                id).id
        except Exception:
            target_id = int(id)

        client.area.links[str(target_id)]["target_pos"] = pos
        client.send_ooc(
            f'Area {client.area.name} link {target_id}\'s target pos set to "{pos}".'
        )
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_peekable(client, areas):
    """
    Make the path(s) leading to target area(s) /peek-able.
    Usage:  /link_peekable <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)

            client.area.links[str(target_id)]["can_peek"] = True
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(
                f"Area {client.area.name} links {links} are now peekable.")
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_unpeekable(client, areas):
    """
    Make the path(s) leading to target area(s) no longer /peek-able.
    Usage:  /link_unpeekable <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)

            client.area.links[str(target_id)]["can_peek"] = False
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(
                f"Area {client.area.name} links {links} are no longer peekable."
            )
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_seethrough(client, areas):
    """
    Make the path(s) leading to target area(s) see-through. Clients in this
    area automatically see the target's presence and passing messages.
    Usage:  /link_seethrough <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)

            client.area.links[str(target_id)]["seethrough"] = True
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(
                f"Area {client.area.name} links {links} are now see-through.")
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(Arg("areas", variadic=True, help="area IDs"))
def ooc_cmd_link_unseethrough(client, areas):
    """
    Make the path(s) leading to target area(s) no longer see-through.
    Usage:  /link_unseethrough <id(s)>
    """
    try:
        links = []
        for aid in areas:
            try:
                target_id = client.area.area_manager.get_area_by_abbreviation(
                    aid).id
            except Exception:
                target_id = int(aid)

            client.area.links[str(target_id)]["seethrough"] = False
            links.append(target_id)
        if len(links) > 0:
            links = ", ".join(str(link) for link in links)
            client.send_ooc(
                f"Area {client.area.name} links {links} are no longer see-through."
            )
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number or abbreviation.")
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(
    Arg("id", help="area ID"),
    Arg("evidences", int, variadic=True, default=[], help="evidence IDs (blank shows current)"),
)
def ooc_cmd_link_evidence(client, id, evidences):
    """
    Make specific link only accessible from evidence ID(s).
    Pass evidence ID's which you can see by mousing over evidence, or blank to see current evidences.
    Usage:  /link_evidence <id> [evi_id(s)]
    """
    link = None
    evidences = [evi - 1 for evi in evidences]
    try:
        link = client.area.links[id]
        for evi_id in evidences:
            client.area.evi_list.evidences[
                evi_id
            ]  # Test if we can access target evidence
    except IndexError:
        raise ArgumentError("Evidence not found.")
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number.")
    except (AreaError, ClientError):
        raise
    else:
        if len(evidences) > 0:
            link["evidence"] = evidences

        if len(link["evidence"]) > 0:
            evi_list = ", ".join(str(evi + 1) for evi in link["evidence"])
            client.send_ooc(
                f"Area {client.area.name} link {id} associated evidence IDs: {evi_list}."
            )
        else:
            client.send_ooc(
                f"Area {client.area.name} link {id} has no associated evidence."
            )


@mod_only(area_owners=True)
@command(
    Arg("id", help="area ID"),
    Arg("evidences", int, variadic=True, default=[], help="evidence IDs (blank clears all)"),
)
def ooc_cmd_unlink_evidence(client, id, evidences):
    """
    Unlink evidence from links.
    Pass evidence ID's which you can see by mousing over evidence.
    Usage:  /unlink_evidence <aid> [evi_id(s)]
    """
    link = None
    evidences = [evi - 1 for evi in evidences]
    try:
        link = client.area.links[id]
    except (ValueError, KeyError):
        raise ArgumentError("Area ID must be a number.")
    except (AreaError, ClientError):
        raise
    else:
        if len(evidences) > 0:
            link["evidence"] = link["evidence"] - evidences
            evi_list = ", ".join(str(evi + 1) for evi in evidences)
            client.send_ooc(
                f"Area {client.area.name} link {id} is now unlinked from evidence IDs: {evi_list}."
            )
        else:
            link["evidence"] = []
            client.send_ooc(
                f"Area {client.area.name} link {id} associated evidences cleared."
            )


@command(Arg("arg", rest=True, default="", help="<id> [password]"))
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
@command(Arg("arg", rest=True, default="", help="<id/!link> [password]"))
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
