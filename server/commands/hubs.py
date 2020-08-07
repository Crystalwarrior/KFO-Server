import os

import oyaml as yaml #ordered yaml

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ArgumentError, AreaError

from . import mod_only

__all__ = [
    # Navigation
    'ooc_cmd_hub',
    # Saving/loading
    'ooc_cmd_save_hub',
    'ooc_cmd_load_hub',
    'ooc_cmd_list_hubs',
    'ooc_cmd_clear_hub',
    # Area Creation system
    'ooc_cmd_area_create',
    'ooc_cmd_area_remove',
    'ooc_cmd_area_rename',
    'ooc_cmd_area_swap',
    'ooc_cmd_area_pref',
    'ooc_cmd_area_move_delay',
    'ooc_cmd_hub_move_delay',
    'ooc_cmd_hub_arup_enable',
    'ooc_cmd_hub_arup_disable',
    'ooc_cmd_hub_hide_clients',
    'ooc_cmd_hub_unhide_clients',
    # General
    'ooc_cmd_follow',
    'ooc_cmd_unfollow',
    'ooc_cmd_info',
    'ooc_cmd_gm',
    'ooc_cmd_ungm',
    'ooc_cmd_broadcast',
    'ooc_cmd_clear_broadcast',
]


def ooc_cmd_hub(client, arg):
    """
    List hubs, or go to another hub.
    Usage: /hub [id] or /hub [name]
    """
    args = arg.split()
    if len(args) == 0:
        client.send_hub_list()
        return

    try:
        for hub in client.server.hub_manager.hubs:
            if (args[0].isdigit() and hub.id == int(args[0])) or hub.name.lower() == arg.lower() or hub.abbreviation == args[0]:
                if hub == client.area.area_manager:
                    raise AreaError('User already in specified hub.')
                preflist = client.server.supported_features.copy()
                if not hub.arup_enabled:
                    preflist.remove('arup')
                client.send_command('FL', preflist)
                client.change_area(hub.default_area())
                client.send_hub_info()
                return
        raise AreaError('Targeted hub not found!')
    except ValueError:
        raise ArgumentError('Hub ID must be a name, abbreviation or a number.')
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_save_hub(client, arg):
    """
    Save the current Hub in the server's storage/hubs/<name>.yaml file.
    Usage: /save_hub <name>
    """
    if not client.is_mod:
        if arg == '':
            raise ArgumentError('You must be authorized to save the default hub!')
        if len(arg) < 3:
            raise ArgumentError("Filename must be at least 3 symbols long!")
    try:
        if arg != '':
            path = 'storage/hubs'
            num_files = len([f for f in os.listdir(
                path) if os.path.isfile(os.path.join(path, f))])
            if (num_files >= 1000): #yikes
                raise AreaError('Server storage full! Please contact the server host to resolve this issue.')
            try:
                arg = f'{path}/{arg}.yaml'
                with open(arg, 'w', encoding='utf-8') as stream:
                    yaml.dump(client.area.area_manager.save(), stream, default_flow_style=False)
            except:
                raise AreaError(f'File path {arg} is invalid!')
            client.send_ooc(f'Saving as {arg}...')
        else:
            client.server.hub_manager.save('config/areas_new.yaml')
            client.send_ooc('Saving all Hubs to areas_new.yaml. Contact the server owner to apply the changes.')
    except AreaError:
        raise


@mod_only(hub_owners=True)
def ooc_cmd_load_hub(client, arg):
    """
    Load Hub data from the server's storage/hubs/<name>.yaml file.
    Usage: /load_hub <name>
    """
    if arg == '' and not client.is_mod:
        raise ArgumentError('You must be authorized to load the default hub!')
    try:
        if arg != '':
            path = 'storage/hubs'
            arg = f'{path}/{arg}.yaml'
            try:
                with open(arg, 'r', encoding='utf-8') as stream:
                    hub = yaml.safe_load(stream)
            except:
                raise AreaError(f'File path {arg} is invalid!')
            client.area.area_manager.load(hub)
            client.send_ooc(f'Loading as {arg}...')
            client.area.area_manager.send_arup_players()
            client.area.area_manager.send_arup_status()
            client.area.area_manager.send_arup_cms()
            client.area.area_manager.send_arup_lock()
            client.server.client_manager.refresh_music(client.area.area_manager.clients)
            client.send_ooc('Success, sending ARUP and refreshing music...')
        else:
            client.server.hub_manager.load()
            client.send_ooc('Loading all Hubs from areas.yaml...')
            clients = set()
            for hub in client.server.hub_manager.hubs:
                hub.send_arup_players()
                hub.send_arup_status()
                hub.send_arup_cms()
                hub.send_arup_lock()
                clients = clients | hub.clients
            client.server.client_manager.refresh_music(clients)
            client.send_ooc('Success, sending ARUP and refreshing music...')

    except AreaError:
        raise


@mod_only()
def ooc_cmd_list_hubs(client, arg):
    """
    Show all the available hubs for loading in the storage/hubs/ folder.
    Usage: /list_hubs
    """
    text = 'Available hubs:'
    for F in os.listdir('storage/hubs/'):
        if F.lower().endswith('.yaml'):
            text += '\n- {}'.format(F[:-5])

    client.send_ooc(text)


@mod_only(hub_owners=True)
def ooc_cmd_clear_hub(client, arg):
    """
    Clear the current hub and reset it to its default state.
    Usage: /clear_hub
    """
    if arg != '':
        raise ArgumentError('This command takes no arguments!')
    try:
        client.server.hub_manager.load(hub_id=client.area.area_manager.id)
        client.area.area_manager.broadcast_ooc('Hub clearing initiated...')
        client.area.area_manager.send_arup_players()
        client.area.area_manager.send_arup_status()
        client.area.area_manager.send_arup_cms()
        client.area.area_manager.send_arup_lock()
        client.server.client_manager.refresh_music(client.area.area_manager.clients)
        client.send_ooc('Success, sending ARUP and refreshing music...')
    except AreaError:
        raise


@mod_only(hub_owners=True)
def ooc_cmd_area_create(client, arg):
    """
    Create a new area.
    Usage: /area_create [name]
    """
    try:
        area = client.area.area_manager.create_area()
        if arg != '':
            area.name = arg
        # Legacy functionality:
        area.evidence_mod = 'HiddenCM'

        client.area.area_manager.broadcast_area_list()
        client.area.area_manager.send_arup_cms()
        client.send_ooc(f'New area created! {area.name} ({len(client.area.area_manager.areas)}/{client.area.area_manager.max_areas})')
    except AreaError:
        raise


@mod_only(hub_owners=True)
def ooc_cmd_area_remove(client, arg):
    """
    Remove specified area by Area ID.
    Usage: /area_remove <aid>
    """
    args = arg.split()

    if len(args) == 1:
        try:
            area = client.area.area_manager.get_area_by_id(int(args[0]))
            name = area.name
            client.area.area_manager.remove_area(area)
            client.area.area_manager.broadcast_area_list()
            client.send_ooc(f'Area {name} removed!')
        except ValueError:
            raise ArgumentError('Area ID must be a number.')
        except (AreaError, ClientError):
            raise
    else:
        raise ArgumentError('Invalid number of arguments. Use /area_remove <aid>.')


@mod_only(hub_owners=True)
def ooc_cmd_area_rename(client, arg):
    """
    Rename area you are currently in to <name>.
    Usage: /area_rename <name>
    """
    if arg != '':
        try:
            client.area.name = arg
            client.area.area_manager.broadcast_area_list()
            client.send_ooc(f'Renamed area {client.area.id} to {client.area.name}.')
        except ValueError:
            raise ArgumentError('Area ID must be a number.')
        except (AreaError, ClientError):
            raise
    else:
        raise ArgumentError('Invalid number of arguments. Use /area_rename <name>.')


@mod_only(hub_owners=True)
def ooc_cmd_area_swap(client, arg):
    """
    Swap areas by Area IDs <aid1> and <aid2>.
    Usage: /area_rename <aid1> <aid2>
    """
    args = arg.split()
    if len(args) != 2:
        raise ClientError("You must specify 2 numbers.")
    try:
        area1 = client.area.area_manager.get_area_by_id(int(args[0]))
        area2 = client.area.area_manager.get_area_by_id(int(args[1]))
        client.area.area_manager.swap_area(area1, area2)
        client.area.area_manager.broadcast_area_list()
        client.send_ooc(f'Area {area1.name} has been swapped with Area {area2.name}!')
    except ValueError:
        raise ArgumentError('Area IDs must be a number.')
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
def ooc_cmd_area_pref(client, arg):
    """
    Toggle a preference on/off for an area.
    Usage:  /area_pref - display list of prefs
            /area_pref <pref> - toggle pref on/off
            /area_pref <pref> <on/true|off/false> - set pref to on or off
    """
    cm_allowed = [
        'locking_allowed',
        'iniswap_allowed',
        'showname_changes_allowed',
        'shouts_allowed',
        'jukebox',
        'non_int_pres_only',
        'blankposting_allowed',
        'hide_clients',
        'music_autoplay',
        'replace_music',
        'client_music',
        'can_dj',
        'hidden',
        'can_whisper',
        'can_wtce',
    ]

    if len(arg) == 0:
        msg = 'Current preferences:'
        for attri in client.area.__dict__.keys():
            value = getattr(client.area, attri)
            if not(type(value) is bool):
                continue
            mod = '[gm] ' if not (attri in cm_allowed) else ''
            msg += f'\n* {mod}{attri}={value}'
        client.send_ooc(msg)
        return

    args = arg.split()
    if len(args) > 2:
        raise ArgumentError("Usage: /area_pref | /area_pref <pref> | /area_pref <pref> <on|off>")

    try:
        attri = getattr(client.area, args[0].lower())
        if not (type(attri) is bool):
            raise ArgumentError("Preference is not a boolean.")
        if not client.is_mod and not client in client.area.area_manager.owners and not (args[0] in cm_allowed):
            raise ClientError("You need to be a GM to modify this preference.")
        tog = not attri
        if len(args) > 1:
            if args[1].lower() in ('on', 'true'):
                tog = True
            elif args[1].lower() in ('off', 'false'):
                tog = False
            else:
                raise ArgumentError("Invalid argument: {}".format(arg))
        client.send_ooc(f'Setting preference {args[0]} to {tog}...')
        setattr(client.area, args[0], tog)
        database.log_room(args[0], client, client.area, message=f'Setting preference to {tog}')
    except ValueError:
        raise ArgumentError('Invalid input.')
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
def ooc_cmd_area_move_delay(client, arg):
    """
    Set the area's move delay to a value in seconds. Can be negative.
    Delay must be from -1800 to 1800 in seconds or empty to check.
    Usage: /area_move_delay [delay]
    """
    args = arg.split()
    try:
        if len(args) > 0:
            move_delay = min(1800, max(-1800, int(args[0]))) # Move delay is limited between -1800 and 1800
            client.area.move_delay = move_delay
            client.send_ooc(f'Set {client.area.name} movement delay to {move_delay}.')
        else:
            client.send_ooc(f'Current move delay for {client.area.name} is {client.area.move_delay}.')
    except ValueError:
        raise ArgumentError('Delay must be an integer between -1800 and 1800.')
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_hub_move_delay(client, arg):
    """
    Set the hub's move delay to a value in seconds. Can be negative.
    Delay must be from -1800 to 1800 in seconds or empty to check.
    Usage: /hub_move_delay [delay]
    """
    args = arg.split()
    try:
        if len(args) > 0:
            move_delay = min(1800, max(-1800, int(args[0]))) # Move delay is limited between -1800 and 1800
            client.area.area_manager.move_delay = move_delay
            client.send_ooc(f'Set {client.area.name} movement delay to {move_delay}.')
        else:
            client.send_ooc(f'Current move delay for {client.area.name} is {client.area.area_manager.move_delay}.')
    except ValueError:
        raise ArgumentError('Delay must be an integer between -1800 and 1800.')
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_hub_arup_enable(client, arg):
    """
    Enable the ARUP system for this hub.
    Usage: /hub_arup_enable
    """
    if client.area.area_manager.arup_enabled:
        raise ClientError('ARUP system is already enabled! Use /arup_disable to disable it.')
    client.area.area_manager.arup_enabled = True
    client.area.area_manager.send_command('FL', client.server.supported_features)
    client.area.area_manager.broadcast_area_list()
    client.area.area_manager.broadcast_ooc('ARUP system has been enabled for this hub.')


@mod_only(hub_owners=True)
def ooc_cmd_hub_arup_disable(client, arg):
    """
    Disable the ARUP system for this hub.
    Usage: /hub_arup_disable
    """
    if not client.area.area_manager.arup_enabled:
        raise ClientError('ARUP system is already disabled! Use /arup_enable to enable it.')
    client.area.area_manager.arup_enabled = False
    preflist = client.server.supported_features.copy()
    preflist.remove('arup')
    client.area.area_manager.send_command('FL', preflist)
    client.area.area_manager.broadcast_area_list()
    client.area.area_manager.broadcast_ooc('ARUP system has been disabled for this hub.')


@mod_only(hub_owners=True)
def ooc_cmd_hub_hide_clients(client, arg):
    """
    Hide the playercounts for this Hub's areas.
    Usage: /hub_hide_clients
    """
    if client.area.area_manager.hide_clients:
        raise ClientError('Client playercounts already hidden! Use /hub_unhide_clients to unhide.')
    client.area.area_manager.hide_clients = True
    client.area.area_manager.broadcast_area_list()
    client.area.area_manager.broadcast_ooc('Client playercounts are now hidden for this hub.')


@mod_only(hub_owners=True)
def ooc_cmd_hub_unhide_clients(client, arg):
    """
    Unhide the playercounts for this Hub's areas.
    Usage: /hub_unhide_clients
    """
    if not client.area.area_manager.hide_clients:
        raise ClientError('Client playercounts already revealed! Use /hub_hide_clients to hide.')
    client.area.area_manager.hide_clients = False
    client.area.area_manager.broadcast_area_list()
    client.area.area_manager.broadcast_ooc('Client playercounts are no longer hidden for this hub.')


def ooc_cmd_follow(client, arg):
    if len(arg) == 0:
        try:
            c = client.server.client_manager.get_targets(client, TargetType.ID, int(client.following), False)[0]
            client.send_ooc(
                f'You are currently following [{c.id}] {c.char_name}.')
        except:
            raise ArgumentError('You must specify a target. Use /follow <id>.')
        return
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /follow <id>.')
    if targets:
        c = targets[0]
        if client == c:
            raise ClientError('Can\'t follow yourself!')
        if c not in client.area.clients and not client.is_mod and not client in client.area.area_manager.owners:
            raise ClientError('You are not a mod/GM - Target must be present in your area!')
        if client.following == c.id:
            raise ClientError(
                f'Already following [{c.id}] {c.char_name}!')
        client.following = c.id
        client.send_ooc(
            f'You are now following [{c.id}] {c.char_name}.')
        client.change_area(c.area)
    else:
        client.send_ooc('No targets found.')


def ooc_cmd_unfollow(client, arg):
    try:
        c = client.server.client_manager.get_targets(
            client, TargetType.ID, int(client.following), False)[0]
        client.send_ooc(
            f'You are no longer following [{c.id}] {c.char_name}.')
        client.following = None
    except:
        client.following = None
        raise ClientError('You\'re not following anyone!')


def ooc_cmd_info(client, arg):
    """
    Check the information for the current Hub
    Usage: /info [str]
    """
    if len(arg) == 0:
        client.send_hub_info()
        database.log_room('info.request', client, client.area)
    else:
        if not client.is_mod and not client in client.area.area_manager.owners:
            raise ClientError('You must be a GM of the Hub to do that.')
        client.area.area_manager.info = arg
        client.area.area_manager.broadcast_ooc('{} changed the Hub info.'.format(
            client.char_name))
        database.log_room('info.change', client, client.area, message=arg)


def ooc_cmd_gm(client, arg):
    """
    Add a game master for the current Hub.
    Usage: /gm <id>
    """
    if not client.area.area_manager.can_gm:
        raise ClientError('You can\'t become a GM in this Hub!')
    if len(client.area.area_manager.owners) == 0:
        if len(arg) > 0:
            raise ArgumentError(
                'You cannot \'nominate\' people to be GMs when you are not one.'
            )
        client.area.area_manager.add_owner(client)
        database.log_room('gm.add', client, client.area, target=client, message='self-added')
    elif client in client.area.area_manager.owners:
        if len(arg) > 0:
            arg = arg.split(' ')
        for id in arg:
            try:
                id = int(id)
                c = client.server.client_manager.get_targets(
                    client, TargetType.ID, id, False)[0]
                if not c in client.area.area_manager.clients:
                    raise ArgumentError(
                        'You can only \'nominate\' people to be GMs when they are in the hub.'
                    )
                elif c in client.area.area_manager.owners:
                    client.send_ooc(
                        f'{c.char_name} [{c.id}] is already a GM here.')
                else:
                    client.area.area_manager.add_owner(c)
                    database.log_room('gm.add', client, client.area, target=c)
            except ValueError:
                client.send_ooc(
                    f'{id} does not look like a valid ID.')
            except (ClientError, ArgumentError):
                raise
    else:
        raise ClientError('You must be authorized to do that.')


@mod_only(hub_owners=True)
def ooc_cmd_ungm(client, arg):
    """
    Remove a game master from the current Hub.
    Usage: /ungm <id>
    """
    if len(arg) > 0:
        arg = arg.split()
    else:
        arg = [client.id]
    for _id in arg:
        try:
            _id = int(_id)
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, _id, False)[0]
            if c in client.area.area_manager.owners:
                client.area.area_manager.remove_owner(c)
                database.log_room('gm.remove', client, client.area, target=c)
            else:
                client.send_ooc(
                    'You cannot remove someone from GMing when they aren\'t a GM.'
                )
        except ValueError:
            client.send_ooc(
                f'{id} does not look like a valid ID.')
        except (ClientError, ArgumentError):
            raise


@mod_only(area_owners=True)
def ooc_cmd_broadcast(client, arg):
    """
    Start broadcasting your IC, Music and Judge buttons to specified area ID's.
    Usage: /broadcast <id(s)>
    """
    args = arg.split()
    if len(args) <= 0:
        a_list = ', '.join([str(a.id) for a in client.broadcast_list])
        client.send_ooc(f'Your broadcast list is {a_list}')
        return
    try:
        client.broadcast_list.clear()
        for aid in args:
            area = client.area.area_manager.get_area_by_id(int(aid))
            client.broadcast_list.append(area)
        a_list = ', '.join([str(a.id) for a in client.broadcast_list])
        client.send_ooc(f'Your broadcast list is now {a_list}')
    except ValueError:
        client.send_ooc('Bad arguments!')
    except (ClientError, AreaError):
        raise

def ooc_cmd_clear_broadcast(client, arg):
    """
    Stop broadcasting your IC, Music and Judge buttons.
    Usage: /broadcast <id(s)>
    """
    if len(client.broadcast_list) <= 0:
        client.send_ooc('Your broadcast list is already empty!')
        return
    client.broadcast_list.clear()
    client.send_ooc('Your broadcast list has been cleared.')