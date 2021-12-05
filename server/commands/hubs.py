import os
import shlex
import oyaml as yaml #ordered yaml
from server import area
from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ArgumentError, AreaError
from server.constants import dezalgo

from . import mod_only

__all__ = [
    # Navigation
    'ooc_cmd_hub',
    # Saving/loading
    'ooc_cmd_save_hub',
    'ooc_cmd_load_hub',
    'ooc_cmd_list_hubs',
    'ooc_cmd_clear_hub',
    'ooc_cmd_rename_hub',
    # Area Creation system
    'ooc_cmd_can_getarea',
    'ooc_cmd_area_create',
    'ooc_cmd_area_remove',
    'ooc_cmd_area_rename',
    'ooc_cmd_area_swap',
    'ooc_cmd_area_switch',
    'ooc_cmd_area_pref',
    'ooc_cmd_area_move_delay',
    'ooc_cmd_hub_move_delay',
    'ooc_cmd_toggle_replace_music',
    'ooc_cmd_arup_enable',
    'ooc_cmd_arup_disable',
    'ooc_cmd_toggle_getareas',
    'ooc_cmd_toggle_spectate',
    'ooc_cmd_hide_clients',
    'ooc_cmd_unhide_clients',
    # General
    'ooc_cmd_follow',
    'ooc_cmd_unfollow',
    'ooc_cmd_info',
    'ooc_cmd_gm',
    'ooc_cmd_ungm',
    'ooc_cmd_broadcast',
    'ooc_cmd_clear_broadcast',
    'ooc_cmd_area_say',
]


@mod_only(hub_owners=True)
def ooc_cmd_area_say(client, arg):
  args = shlex.split(arg)
  if len(args) > 1:
     say = True
     client.area.sayallow(say, args[0], args[1])
     client.send_ooc('Frase impostata')
  else:
     say = False
     client.area.sayallow(say)
     client.send_ooc('Frase disattivata')
  
def ooc_cmd_hub(client, arg):
    """
    Fornisce una lista di hubs e permette di muoverti tra esse.
    Uso: /hub [id/name]
    """
    if arg == '':
        client.send_hub_list()
        return

    try:
        for hub in client.server.hub_manager.hubs:
            h = arg.split(' ')[0]
            hid = h.strip('[]')
            if (h.startswith('[') and h.endswith(']') and \
                    hid.isdigit() and hub.id == int(hid)) or \
                    hub.name.lower() == arg.lower() or hub.abbreviation == arg or \
                        (arg.isdigit() and hub.id == int(arg)):
                if hub == client.area.area_manager:
                    raise ClientError('User already in specified hub.')
                preflist = client.server.supported_features.copy()
                if not hub.arup_enabled or client.viewing_hub_list:
                    preflist.remove('arup')
                client.send_command('FL', *preflist)
                client.send_ooc(f'Changed to hub [{hub.id}] {hub.name}.')
                client.change_area(hub.default_area())
                client.area.area_manager.send_arup_players([client])
                client.area.area_manager.send_arup_status([client])
                client.area.area_manager.send_arup_cms([client])
                client.area.area_manager.send_arup_lock([client])
                client.send_hub_info()
                return
        raise AreaError('Targeted hub not found!')
    except ValueError:
        raise ArgumentError('Hub ID must be a name, abbreviation or a number.')
    except (AreaError, ClientError):
        raise

@mod_only(hub_owners=True)
def ooc_cmd_can_getarea(client, arg):
   if client.area.area_manager.can_getarea:
     client.area.area_manager.can_getarea = False
     client.send_ooc('Nessuno potrà usare il comando getarea')
   else:
     client.area.area_manager.can_getarea = True
     client.send_ooc('Comando getarea ripristinato')

@mod_only(hub_owners=True)
def ooc_cmd_can_getareas(client, arg):
   if client.area.area_manager.can_getareas:
     client.area.area_manager.can_getareas = False
     client.send_ooc('Nessuno potrà usare i comandi getareas e gethubs')
   else:
     client.area.area_manager.can_getareas = True
     client.send_ooc('Comandi getareas e gethubs ripristinati')

@mod_only(hub_owners=True)
def ooc_cmd_save_hub(client, arg):
    """
    Salva l'Hub corrente all'interno del server (storage/hubs/<name>.yaml).
    Se viene lasciato vuoto e sei mod, verrà salvato nella configurazione (config/areas_new.yaml) in attesa che venga approvato dall'owner o dal co.
    Uso: /save_hub <name>
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
                if os.path.isfile(arg):
                    with open(arg, 'r', encoding='utf-8') as stream:
                        hub = yaml.safe_load(stream)
                    if 'read_only' in hub and hub['read_only'] == True:
                        raise ArgumentError(f'Hub {arg} already exists and it is read-only!')
                with open(arg, 'w', encoding='utf-8') as stream:
                    yaml.dump(client.area.area_manager.save(ignore=['can_gm', 'max_areas']), stream, default_flow_style=False)
            except ArgumentError:
                raise
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
    Carica le info di un Hub dai files all'interno del server (storage/hubs/<name>.yaml).
    Uso: /load_hub <name>
    """
    if arg == '' and not client.is_mod:
        raise ArgumentError('You must be authorized to load the default hub!')
    try:
        if arg != '':
            path = 'storage/hubs'
            arg = f'{path}/{arg}.yaml'
            if not os.path.isfile(arg):
                raise ArgumentError(f'File not found: {arg}')
            with open(arg, 'r', encoding='utf-8') as stream:
                hub = yaml.safe_load(stream)
            client.area.area_manager.load(hub, ignore=['can_gm', 'max_areas'])
            client.send_ooc(f'Loading as {arg}...')
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
                hub.send_arup_status()
                hub.send_arup_cms()
                hub.send_arup_lock()
                clients = clients | hub.clients
            client.server.client_manager.refresh_music(clients)
            client.send_ooc('Success, sending ARUP and refreshing music...')

    except Exception as ex:
        msg = f'There is a problem: {ex}'
        msg += '\nContact the server owner for support.'
        client.send_ooc(msg)

@mod_only()
def ooc_cmd_list_hubs(client, arg):
    """
    Mostra tutte le hubs disponibili da caricare nei files del server (storage/hubs/folder).
    Uso: /list_hubs
    """
    text = 'Available hubs:'
    for F in os.listdir('storage/hubs/'):
        if F.lower().endswith('.yaml'):
            text += '\n- {}'.format(F[:-5])

    client.send_ooc(text)


@mod_only(hub_owners=True)
def ooc_cmd_clear_hub(client, arg):
    """
    "Pulisce" l'hub attuale e lo riporta al suo stato di default.
    Uso: /clear_hub
    """
    if arg != '':
        raise ArgumentError('This command takes no arguments!')
    try:
        client.server.hub_manager.load(hub_id=client.area.area_manager.id)
        client.area.area_manager.broadcast_ooc('Hub clearing initiated...')
        client.server.client_manager.refresh_music(client.area.area_manager.clients)
        client.send_ooc('Success, sending ARUP and refreshing music...')
    except AreaError:
        raise


@mod_only(hub_owners=True)
def ooc_cmd_rename_hub(client, arg):
    """
    Rinomina l'hub in cui ti trovi attualmente.
    Uso: /rename_hub <name>
    """
    if arg != '':
        client.area.area_manager.name = dezalgo(arg)[:64]
        client.send_ooc(f'Renamed hub [{client.area.area_manager.id}] to {client.area.area_manager.name}.')
    else:
        raise ArgumentError('Invalid number of arguments. Use /rename_hub <name>.')


@mod_only(hub_owners=True)
def ooc_cmd_area_create(client, arg):
    """
    Crea una nuova area.
    Le aree appena create avranno le impostazioni delle prove su HiddenCM.
    Uso: /area_create [name]
    """
    try:
        area = client.area.area_manager.create_area()
        if arg != '':
            area.name = arg
        # Legacy functionality:
        area.evidence_mod = 'HiddenCM'

        client.area.area_manager.broadcast_area_list()
        client.send_ooc(f'New area created! {area.name} ({len(client.area.area_manager.areas)}/{client.area.area_manager.max_areas})')
    except AreaError:
        raise


@mod_only(hub_owners=True)
def ooc_cmd_area_remove(client, arg):
    """
    Rimuove una specificata area tramite l'ID.
    Uso: /area_remove <id>
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


@mod_only(area_owners=True)
def ooc_cmd_area_rename(client, arg):
    """
    Rinomina l'area in cui ti trovi attualmente.
    Uso: /area_rename <name>
    """
    if arg != '':
        client.area.name = dezalgo(arg)[:64]
        # Renaming doesn't change the actual area objects in that list so we have to tell it manually
        client.area.area_manager.broadcast_area_list(refresh=True)
        client.send_ooc(f'Renamed area [{client.area.id}] to {client.area.name}.')
    else:
        raise ArgumentError('Invalid number of arguments. Use /area_rename <name>.')


@mod_only(hub_owners=True)
def ooc_cmd_area_swap(client, arg):
    """
    Permette di scambiare due aree tramite ID correggendo i collegamenti per fare riferimento all'area giusta.
    Uso: /area_swap <id> <id>
    """
    args = arg.split()
    if len(args) != 2:
        raise ClientError("You must specify 2 numbers.")
    try:
        area1 = client.area.area_manager.get_area_by_id(int(args[0]))
        area2 = client.area.area_manager.get_area_by_id(int(args[1]))
        client.area.area_manager.swap_area(area1, area2, True)
        client.area.area_manager.broadcast_area_list()
        client.send_ooc(f'Area {area1.name} has been swapped with Area {area2.name}!')
    except ValueError:
        raise ArgumentError('Area IDs must be a number.')
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_area_switch(client, arg):
    """
    Permette di scambiare due aree tramite ID senza correggere i collegamenti.
    Uso: /area_switch <id> <id>
    """
    args = arg.split()
    if len(args) != 2:
        raise ClientError("You must specify 2 numbers.")
    try:
        area1 = client.area.area_manager.get_area_by_id(int(args[0]))
        area2 = client.area.area_manager.get_area_by_id(int(args[1]))
        client.area.area_manager.swap_area(area1, area2, False)
        client.area.area_manager.broadcast_area_list()
        client.send_ooc(f'Area {area1.name} has been switched with Area {area2.name}!')
    except ValueError:
        raise ArgumentError('Area IDs must be a number.')
    except (AreaError, ClientError):
        raise

@mod_only(area_owners=True)
def ooc_cmd_area_pref(client, arg):
    """
    Attiva o disattiva una preferenza per un'area.
    Lascia pref vuoto per vedere le preferenze disponibili.
    Lascia su on/true e off/false per cambiare preferenza.
    Uso:  /area_pref [pref] [on/true/off/false]
    """
    cm_allowed = [
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
        'can_spectate',
        'can_getarea',
        'can_cross_swords',
        'can_scrum_debate',
        'can_panic_talk_action',
        'bg_lock',
        'force_sneak',
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
        cmd = args[0].lower()
        attri = getattr(client.area, cmd)
        if not (type(attri) is bool):
            raise ArgumentError("Preference is not a boolean.")
        if not client.is_mod and not client in client.area.area_manager.owners and not (cmd in cm_allowed):
            raise ClientError("You need to be a GM to modify this preference.")
        tog = not attri
        if len(args) > 1:
            if args[1].lower() in ('on', 'true'):
                tog = True
            elif args[1].lower() in ('off', 'false'):
                tog = False
            else:
                raise ArgumentError("Invalid argument: {}".format(arg))
        client.send_ooc(f'Setting preference {cmd} to {tog}...')
        setattr(client.area, cmd, tog)
        database.log_area('area.pref', client, client.area, message=f'Setting preference {cmd} to {tog}')
    except ValueError:
        raise ArgumentError('Invalid input.')
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
def ooc_cmd_area_move_delay(client, arg):
    """
    Imposta il ritardo di spostamento dell'area. Can be negative.
    Il ritardo deve essere impostato tra i -1800 e 1800 secondi oppure può essere lasciato vuoto per controllare tutti i ritardi applicati.
    Uso: /area_move_delay [delay]
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
    Imposta il ritardo di spostamento dell'hub. Can be negative.
    Il ritardo deve essere impostato tra -1800 e 1800 secondi oppure può essere lasciato vuoto per controllare tutti i ritardi applicati.
    Uso: /hub_move_delay [delay]
    """
    args = arg.split()
    try:
        if len(args) > 0:
            move_delay = min(1800, max(-1800, int(args[0]))) # Move delay is limited between -1800 and 1800
            client.area.area_manager.move_delay = move_delay
            client.send_ooc(f'Set {client.area.area_manager.name} movement delay to {move_delay}.')
        else:
            client.send_ooc(f'Current move delay for {client.area.area_manager.name} is {client.area.area_manager.move_delay}.')
    except ValueError:
        raise ArgumentError('Delay must be an integer between -1800 and 1800.')
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_toggle_replace_music(client, arg):
    """
    Permetti o meno alla lista delle ost dell'hub di sostituire quella della lista delle ost del server.
    Uso: /toggle_replace_music
    """
    client.area.area_manager.replace_music = not client.area.area_manager.replace_music
    toggle = 'now' if client.area.area_manager.replace_music else 'no longer'
    client.server.client_manager.refresh_music(client.area.area_manager.clients)
    client.area.area_manager.broadcast_ooc(f'Hub music list will {toggle} replace server music list.')


@mod_only(hub_owners=True)
def ooc_cmd_arup_enable(client, arg):
    """
    Attiva il sistema dell'Area Update per questo hub.
    Il sistema dell'Area Update (ARUP) è l'informazione extra mostrata nella lista A/M ed è possibile visualizzarla fino a quando è possibile fare /status.
    Uso: /arup_enable
    """
    if client.area.area_manager.arup_enabled:
        raise ClientError('ARUP system is already enabled! Use /arup_disable to disable it.')
    client.area.area_manager.arup_enabled = True
    client.area.area_manager.send_command('FL', client.server.supported_features)
    client.area.area_manager.broadcast_area_list(refresh=True)
    client.area.area_manager.broadcast_ooc('ARUP system has been enabled for this hub.')


@mod_only(hub_owners=True)
def ooc_cmd_arup_disable(client, arg):
    """
    Disattiva il sistema dell'Area Update per questo hub.
    Uso: /arup_disable
    """
    if not client.area.area_manager.arup_enabled:
        raise ClientError('ARUP system is already disabled! Use /arup_enable to enable it.')
    client.area.area_manager.arup_enabled = False
    preflist = client.server.supported_features.copy()
    preflist.remove('arup')
    client.area.area_manager.send_command('FL', *preflist)
    client.area.area_manager.broadcast_area_list(refresh=True)
    client.area.area_manager.broadcast_ooc('ARUP system has been disabled for this hub.')


@mod_only(hub_owners=True)
def ooc_cmd_toggle_getareas(client, arg):
    """
    Attiva o disattiva l'utilizzo del /getareas per i normali utenti nell'hub.
    Uso: /toggle_getareas
    """
    client.area.area_manager.can_getareas = not client.area.area_manager.can_getareas
    toggle = 'enabled' if client.area.area_manager.can_getareas else 'disabled'
    client.area.area_manager.broadcast_ooc(f'Use of /getareas has been {toggle} for this hub.')


@mod_only(hub_owners=True)
def ooc_cmd_toggle_spectate(client, arg):
    """
    Disattiva il sistema dell'Area Update per quest'hub.
    Uso: /toggle_spectate
    """
    client.area.area_manager.can_spectate = not client.area.area_manager.can_spectate
    toggle = 'enabled' if client.area.area_manager.can_spectate else 'disabled'
    client.area.area_manager.broadcast_ooc(f'Spectating has been {toggle} for this hub.')



@mod_only(hub_owners=True)
def ooc_cmd_hide_clients(client, arg):
    """
    Nascondi il numero di utenti nelle aree di quest'Hub.
    Uso: /hide_clients
    """
    if client.area.area_manager.hide_clients:
        raise ClientError('Client playercounts already hidden! Use /unhide_clients to unhide.')
    client.area.area_manager.hide_clients = True
    client.area.area_manager.broadcast_area_list()
    client.area.area_manager.broadcast_ooc('Client playercounts are now hidden for this hub.')


@mod_only(hub_owners=True)
def ooc_cmd_unhide_clients(client, arg):
    """
    Mostra il numero di utenti nelle aree di quest'Hub.
    Uso: /unhide_clients
    """
    if not client.area.area_manager.hide_clients:
        raise ClientError('Client playercounts already revealed! Use /hide_clients to hide.')
    client.area.area_manager.hide_clients = False
    client.area.area_manager.broadcast_area_list()
    client.area.area_manager.broadcast_ooc('Client playercounts are no longer hidden for this hub.')


def ooc_cmd_follow(client, arg):
    """
    Segui il personaggio di un utente attraverso il suo ID.
    Uso: /follow [id]
    """
    if len(arg) == 0:
        try:
            client.send_ooc(
                f'You are currently following [{client.following.id}] {client.following.showname}.')
        except:
            raise ArgumentError('Not following anybody. Use /follow <id>.')
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
                f'Already following [{c.id}] {c.showname}!')
        if client.area != c.area:
            client.change_area(c.area)
        client.following = c
        client.send_ooc(
            f'You are now following [{c.id}] {c.showname}.')
    else:
        client.send_ooc('No targets found.')


def ooc_cmd_unfollow(client, arg):
    """
    Smetti di seguire chiunque stessi seguendo.
    Uso: /unfollow
    """
    try:
        client.send_ooc(
            f'You are no longer following [{client.following.id}] {client.following.showname}.')
        client.following = None
    except:
        client.following = None
        raise ClientError('You\'re not following anyone!')


def ooc_cmd_info(client, arg):
    """
    Controlla le informazioni dell'Hub corrente o impostale.
    Usage: /info [info]
    """
    if len(arg) == 0:
        client.send_hub_info()
        database.log_area('info.request', client, client.area)
    else:
        if not client.is_mod and not client in client.area.area_manager.owners:
            raise ClientError('You must be a GM of the Hub to do that.')
        client.area.area_manager.info = arg
        client.area.area_manager.broadcast_ooc('{} changed the Hub info.'.format(
            client.showname))
        database.log_area('info.change', client, client.area, message=arg)


def ooc_cmd_gm(client, arg):
    """
    Aggiungi un Game Master per l'hub corrente (Simile al CM ma per l'intera Hub e in generale).
    Uso: /gm <id>
    """
    if not client.area.area_manager.can_gm:
        raise ClientError('You can\'t become a GM in this Hub!')
    if len(client.area.area_manager.owners) == 0:
        if len(arg) > 0:
            raise ArgumentError(
                'You cannot \'nominate\' people to be GMs when you are not one.'
            )
        for c in client.server.client_manager.get_multiclients(client.ipid, client.hdid):
            if c in c.area.area_manager.owners:
                raise ClientError('One of your clients is already a GM in another hub!')
        client.area.area_manager.add_owner(client)
        database.log_area('gm.add', client, client.area, target=client, message='self-added')
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
                        f'{c.showname} [{c.id}] is already a GM here.')
                else:
                    for mc in c.server.client_manager.get_multiclients(c.ipid, c.hdid):
                        if mc in mc.area.area_manager.owners and mc.area.area_manager != c.area.area_manager:
                            raise ClientError(f'One of {c.showname} [{c.id}]\'s clients is already a GM in another hub!')
                    client.area.area_manager.add_owner(c)
                    database.log_area('gm.add', client, client.area, target=c)
            except (ValueError, IndexError):
                client.send_ooc(
                    f'{id} does not look like a valid ID.')
            except (ClientError, ArgumentError):
                raise
    else:
        raise ClientError('You must be authorized to do that.')


@mod_only(hub_owners=True)
def ooc_cmd_ungm(client, arg):
    """
    Rimuovi un Game Master dalla Hub corrente.
    Se l'id non viene specificato, il Game Master verrà rimosso a te stesso.
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
                database.log_area('gm.remove', client, client.area, target=c)
            else:
                client.send_ooc(
                    'You cannot remove someone from GMing when they aren\'t a GM.'
                )
        except (ValueError, IndexError):
            client.send_ooc(
                f'{id} does not look like a valid ID.')
        except (ClientError, ArgumentError):
            raise


@mod_only(area_owners=True)
def ooc_cmd_broadcast(client, arg):
    """
    Trasmetti la tua musica IC e i bottoni del giudice ad una specifica Area attraverso l'ID.
    Per includere tutte le aree usa /broadcast all.
    /clear_broadcast per smettere di trasmettere.
    Uso: /broadcast <id(s)>
    """
    args = arg.split()
    if len(args) <= 0:
        a_list = ', '.join([str(a.id) for a in client.broadcast_list])
        client.send_ooc(f'Your broadcast list is {a_list}')
        return
    if arg.lower() == 'all':
        args = []
        for area in client.area.area_manager.areas:
            args.append(area.id)
    try:
        broadcast_list = []
        for aid in args:
            area = client.area.area_manager.get_area_by_id(int(aid))
            broadcast_list.append(area)
        # We don't modify the client.broadcast_list directly until now just in case there's an exception.
        client.broadcast_list = broadcast_list
        a_list = ', '.join([str(a.id) for a in client.broadcast_list])
        client.send_ooc(f'Your broadcast list is now {a_list}')
    except ValueError:
        client.send_ooc('Bad arguments!')
    except (ClientError, AreaError):
        raise

def ooc_cmd_clear_broadcast(client, arg):
    """
    Smetti di trasmettere la IC, musica e i bottoni del giudice.
    Uso: /clear_broadcast
    """
    if len(client.broadcast_list) <= 0:
        client.send_ooc('Your broadcast list is already empty!')
        return
    client.broadcast_list.clear()
    client.send_ooc('Your broadcast list has been cleared.')