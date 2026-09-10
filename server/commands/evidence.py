import yaml
import os

from server import database
from server.constants import derelative
from server.exceptions import ClientError, ArgumentError, AreaError

from . import mod_only, command, Arg

__all__ = [
    "ooc_cmd_evidence",
    "ooc_cmd_evidence_add",
    "ooc_cmd_evidence_remove",
    "ooc_cmd_evidence_edit",
    "ooc_cmd_evidence_present",
    "ooc_cmd_evidence_mod",
    "ooc_cmd_evidence_swap",
    "ooc_cmd_evidence_insert",
    "ooc_cmd_evidence_prefs",
    "ooc_cmd_evidence_pos",
    "ooc_cmd_evidence_dark",
    "ooc_cmd_evidence_save",
    "ooc_cmd_evidence_load",
    "ooc_cmd_evidence_overlay",
    "ooc_cmd_evidence_lists",
]

@command(Arg("arg", rest=True, default="", help="evidence name or id (blank lists all)"))
def ooc_cmd_evidence(client, arg):
    """
    Use /evidence to read all evidence in the area.
    Use /evidence [evi_name/id] to read specific evidence.
    Usage: /evidence [evi_name/id]
    """
    evi_list = client.area.get_evidence_list(client)

    # Just read all area evidence
    if arg == "":
        msg = f"==Evidence in '{client.area.name}'=="
        for i, evi in enumerate(evi_list):
            # 0 = name
            # 1 = desc
            # 2 = image
            evi_msg = f"\n💼[{i+1}]: '{evi[0]}'"  # (🖼️{evi[2]})
            if arg == "" or arg.lower() in evi_msg.lower():
                msg += evi_msg
        msg += "\n\n|| Use /evidence [evi_name/id] to read specific evidence. ||"
        client.send_ooc(msg)
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
                f"Target evidence not found! (/evidence {arg})"
            )
        msg = f"==💼[{i+1}]: '{evidence[0]}=="
        msg += f"\n🖼️Image: {evidence[2]}"
        msg += f"\n📃Desc:\n{evidence[1]}"
        msg += "\n\n|| Use /evidence to read all evidence in the area ||"
        client.send_ooc(msg)
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


@command(
    Arg("name", default="<name>", help="evidence name"),
    Arg("description", default="<description>", help="evidence description"),
    Arg("image", default="empty.png", help="evidence image"),
)
def ooc_cmd_evidence_add(client, name, description, image):
    """
    Add a piece of evidence.
    For sentences with spaces the arg should be surrounded in ""'s, for example /evidence_add Chair "It's a chair." chair.png
    Usage: /evidence_add [name] [desc] [image]
    """
    client.area.evi_list.add_evidence(
        client, name, description, image
    )
    database.log_area("evidence.add", client, client.area)
    client.area.broadcast_evidence_list()
    client.send_ooc(f"You have added evidence '{name}'.")


@command(Arg("arg", rest=True, default="", help="evidence name or id"))
def ooc_cmd_evidence_remove(client, arg):
    """
    Remove a piece of evidence.
    Usage: /evidence_remove <evi_name/id>
    """
    if arg == "":
        raise ArgumentError(
            "Use /evidence_remove <evi_name/id> to remove that piece of evidence."
        )
    try:
        evi_list = client.area.get_evidence_list(client)
        evidence = None
        for i, evi in enumerate(evi_list):
            if (arg.isnumeric() and int(arg) - 1 == i) or arg.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(
                f"Target evidence not found! (/evidence_remove {arg})"
            )
        evi_name = evidence[0]
        if client.area.evi_list.del_evidence(client, i):
            database.log_area("evidence.del", client, client.area)
            client.area.broadcast_evidence_list()
            client.send_ooc(f"You have removed evidence '{evi_name}'.")
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


@command(
    Arg("target_evi", help="evidence name or id"),
    Arg("name", default="*", help="new evidence name"),
    Arg("description", default="*", help="new evidence description"),
    Arg("image", default="*", help="new evidence image"),
)
def ooc_cmd_evidence_edit(client, target_evi, name, description, image):
    """
    Edit a piece of evidence.
    If you don't want to change something, put an * there.
    For sentences with spaces the arg should be surrounded in ""'s, for example /evidence_edit * "It's a chair." chair.png
    Usage: /evidence_edit <evi_name/id> [name] [desc] [image]
    """
    try:
        evi_list = client.area.get_evidence_list(client)
        evidence = None
        for i, evi in enumerate(evi_list):
            if (target_evi.isnumeric() and int(target_evi) - 1 == i) or target_evi.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(
                f"Target evidence not found! (/evidence_edit {target_evi})"
            )
        evi_name = evidence[0]
        evi = (name, description, image, "all")

        if client.area.evi_list.edit_evidence(client, i, evi):
            database.log_area("evidence.edit", client, client.area)
            client.area.broadcast_evidence_list()
            if evi[0] != "*" and evi_name != evi[0]:
                client.send_ooc(
                    f"You have edited evidence '{evi_name}' to '{evi[0]}'."
                )
            else:
                client.send_ooc(f"You have edited evidence '{evi_name}'.")
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


@command(Arg("arg", rest=True, default="", help="evidence name or id (blank stops)"))
def ooc_cmd_evidence_present(client, arg):
    """
    Present a piece of evidence on your next IC message.
    Don't include [id] or make it 0 to stop presenting evidence.
    Usage: /evidence_present [id]
    """
    if arg == "" or arg == "0":
        client.send_ooc("No longer presenting evidence.")
        client.presenting = 0
        return

    try:
        evidence = None
        evi_list = client.area.get_evidence_list(client)
        # Check if evidence we're looking for exists
        for i, evi in enumerate(evi_list):
            print(arg.lower(), evi[0].lower())
            if (arg.isnumeric() and int(arg) - 1 == i) or arg.lower() == evi[0].lower():
                evidence = evi
                break
        if evidence is None:
            raise AreaError(
                f"Target evidence not found! (/evidence_present {arg})"
            )
        client.presenting = i + 1
        client.send_ooc(
            f"Will now present evidence [{client.presenting}] {evidence[0]} on next IC message.")
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
@command(
    Arg("mode", choices=["FFA", "Mods", "CM", "HiddenCM"], default=None, help="mode (blank shows current)"),
)
def ooc_cmd_evidence_mod(client, mode):
    """
    Change the evidence privilege mode. Refer to the documentation
    for more information on the function of each mode.
    Usage: /evidence_mod <FFA|Mods|CM|HiddenCM>
    """
    if mode is None or mode == client.area.evidence_mod:
        client.send_ooc(f"current evidence mod: {client.area.evidence_mod}")
    else:
        if not client.is_mod:
            if client.area.evidence_mod == "Mods":
                raise ClientError(
                    "You must be authorized to change this area's evidence mod from Mod-only."
                )
            if mode == "Mods":
                raise ClientError(
                    "You must be authorized to set the area's evidence to Mod-only."
                )
        client.area.evidence_mod = mode
        client.area.broadcast_evidence_list()
        client.send_ooc(f"current evidence mod: {client.area.evidence_mod}")
        database.log_area("evidence_mod", client, client.area, message=mode)


@mod_only(area_owners=True)
@command(
    Arg("a", int, help="evidence id"),
    Arg("b", int, help="evidence id"),
)
def ooc_cmd_evidence_swap(client, a, b):
    """
    Swap the positions of two evidence items on the evidence list.
    The ID of each evidence can be displayed by mousing over it in 2.8 client,
    or simply its number starting from 1.
    Usage: /evidence_swap <id> <id>
    """
    try:
        client.area.evi_list.evidence_swap(
            client, a - 1, b - 1)
        client.area.broadcast_evidence_list()
    except Exception:
        raise ClientError("you must specify 2 numbers")


@mod_only(area_owners=True)
@command(
    Arg("a", int, help="evidence id to move"),
    Arg("b", int, help="target position"),
)
def ooc_cmd_evidence_insert(client, a, b):
    """
    Move an evidence item to a new position on the evidence list, shifting
    the items in between (unlike /evidence_swap, which exchanges two ids).
    The ID of each evidence can be displayed by mousing over it in 2.8 client,
    or simply its number starting from 1.
    Usage: /evidence_insert <id> <position>
    """
    try:
        client.area.evi_list.evidence_insert(
            client, a - 1, b - 1)
        client.area.broadcast_evidence_list()
    except Exception:
        raise ClientError("you must specify 2 numbers")

def _find_evidence(client, target, usage):
    """
    Resolve an evidence name or 1-based position number to the live
    `Evidence` object in the area's list.
    """
    evi_list = client.area.get_evidence_list(client)
    for i, evi in enumerate(evi_list):
        if (target.isnumeric() and int(target) - 1 == i) or target.lower() == evi[0].lower():
            return client.area.evi_list.evidences[i]
    raise AreaError(f"Target evidence not found! ({usage} {target})")


@mod_only(area_owners=True)
@command(
    Arg("target_evi", default="", help="evidence name or id"),
    Arg("pref", default="", help="preference name (can_hide_in/can_take/editable)"),
    Arg("tog", bool, default=None, help="on/off"),
)
def ooc_cmd_evidence_prefs(client, target_evi, pref, tog):
    """
    Toggle a boolean property on/off for an evidence item.
    Properties: can_hide_in, can_take, editable.
    Leave pref out to see that evidence's properties.
    Leave value out to toggle the property.
    Usage: /evidence_prefs [evi_name/id] [pref] [on/true/off/false]
    """
    if not target_evi:
        msg = "Evidence properties in this area:"
        for evi in client.area.evi_list.evidences:
            msg += (
                f"\n💼 '{evi.name}'"
                f"\n   pos={evi.pos} | show_in_dark={evi.show_in_dark}"
                f"\n   can_hide_in={evi.can_hide_in} | can_take={evi.can_take} | editable={evi.editable}"
            )
        client.send_ooc(msg)
        return

    evi = _find_evidence(client, target_evi, "[evi_name/id]")
    cmd = pref.lower()
    if cmd not in ("can_hide_in", "can_take", "editable"):
        client.send_ooc(
            f"Evidence '{evi.name}' properties:\n"
            f"* can_hide_in={evi.can_hide_in}\n"
            f"* can_take={evi.can_take}\n"
            f"* editable={evi.editable}"
        )
        return

    tog = not getattr(evi, cmd) if tog is None else tog
    setattr(evi, cmd, tog)
    client.send_ooc(f"Setting evidence property '{cmd}' to {tog} for '{evi.name}'.")
    database.log_area("evidence.pref", client, client.area, message=f"Setting property {cmd} to {tog}")
    client.area.broadcast_evidence_list()


@mod_only(area_owners=True)
@command(
    Arg("target_evi", help="evidence name or id"),
    Arg("pos", default="", help="'all', 'hidden' or positions like def,pro (blank shows current)"),
)
def ooc_cmd_evidence_pos(client, target_evi, pos):
    """
    Show or set the position(s) where an evidence item is visible.
    Use 'all' for every position, 'hidden' for none, or a comma-separated
    list like def,pro for specific positions.
    Usage: /evidence_pos <evi_name/id> [pos]
    """
    evi = _find_evidence(client, target_evi, "<evi_name/id>")
    if not pos:
        client.send_ooc(f"Evidence '{evi.name}' is visible at: {evi.pos}")
        return
    evi.pos = pos.strip() or "all"
    client.send_ooc(f"Evidence '{evi.name}' is now visible at: {evi.pos}")
    database.log_area("evidence.pos", client, client.area, message=evi.pos)
    client.area.broadcast_evidence_list()


@mod_only(area_owners=True)
@command(
    Arg("target_evi", help="evidence name or id"),
    Arg("value", int, default=None, help="0/1/2 (blank shows current)"),
)
def ooc_cmd_evidence_dark(client, target_evi, value):
    """
    Show or set how an evidence item behaves in dark areas.
    0 = hidden in dark, 1 = shown in dark, 2 = ONLY shown in dark.
    Usage: /evidence_dark <evi_name/id> [0/1/2]
    """
    evi = _find_evidence(client, target_evi, "<evi_name/id>")
    if value is None:
        client.send_ooc(f"Evidence '{evi.name}' show_in_dark is: {evi.show_in_dark}")
        return
    if value < 0 or value > 2:
        raise ArgumentError("show_in_dark must be 0, 1 or 2.")
    evi.show_in_dark = value
    client.send_ooc(f"Evidence '{evi.name}' show_in_dark set to {evi.show_in_dark}.")
    database.log_area("evidence.dark", client, client.area, message=value)
    client.area.broadcast_evidence_list()


@mod_only(hub_owners=True)
@command()
def ooc_cmd_evidence_lists(client):
    """
    Show all evidence lists available on the server.
    Usage: /evidence_lists
    """
    msg = "Available Evidence Lists:"
    for F in os.listdir("storage/evidence/"):
        if F.lower().endswith(".yaml"):
            msg += "\n- {}".format(F[:-5])

    client.send_ooc(msg)


def evidence_load(client, name, overlay = False):
    if f"{name}.yaml" not in os.listdir("storage/evidence"):
        client.send_ooc(f"Evidence List {name} not found!")
        return

    with open(f"storage/evidence/{name}.yaml", "r", encoding="utf-8") as stream:
        evidence = yaml.safe_load(stream)

        done_what = "overlay"
        if not overlay:
            client.area.evi_list.evidences.clear()
            done_what = "load"

        client.area.evi_list.import_evidence(evidence)
        client.area.broadcast_evidence_list()
        database.log_area(f"evidence.{done_what}", client, client.area, name)
        client.send_ooc(f"You have {done_what}ed evidence from '{name}'.")


@mod_only(area_owners=True)
@command(Arg("arg", rest=True, default="", help="evidence list name"))
def ooc_cmd_evidence_load(client, arg):
    """
    Allow you to load an evidence list from the server.
    Usage: /evidence_load <name>
    """
    if arg == "":
        client.send_ooc("Usage: /evidence_load <name>")
        return
    evidence_load(client, derelative(arg))


@mod_only(area_owners=True)
@command(Arg("arg", rest=True, default="", help="evidence list name"))
def ooc_cmd_evidence_overlay(client, arg):
    """
    Allow you to load and overlay an evidence list from the server to the existing evidence.
    Usage: /evidence_overlay <name>
    """
    if arg == "":
        client.send_ooc("Usage: /evidence_overlay <name>")
        return
    evidence_load(client, derelative(arg), overlay = True)


@mod_only(area_owners=True)
@command(Arg("arg", rest=True, default="", help="evidence list name"))
def ooc_cmd_evidence_save(client, arg):
    """
    Allow you to save evidence in a list stored in the server files!
    Usage: /evidence_save <name>
    """
    if arg == "":
        client.send_ooc("Usage: /evidence_save <name>")
        return

    if len(client.area.evi_list.evidences) <= 0:
        client.send_ooc("There is no evidence in the area to save!")
        return
    evidence = client.area.evi_list.export_evidence()
    arg = f"storage/evidence/{derelative(arg)}.yaml"
    if os.path.isfile(arg):
        with open(arg, "r", encoding="utf-8") as stream:
            evi_list = yaml.safe_load(stream)
        if "read_only" in evi_list and evi_list["read_only"] is True:
            raise ArgumentError(
                f"Evidence List {arg} already exists and it is read-only!"
            )
    with open(arg, "w", encoding="utf-8") as yaml_save:
        yaml.dump(evidence, yaml_save)
    database.log_area(f"evidence.save", client, client.area, arg)
    client.send_ooc(
        f"Evidence has been saved as '{arg}' on the server."
    )
