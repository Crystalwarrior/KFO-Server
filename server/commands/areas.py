import os

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ArgumentError, AreaError

from . import mod_only

__all__ = [
    'ooc_cmd_bg',
    'ooc_cmd_bgs',
    'ooc_cmd_status',
    'ooc_cmd_area',
    'ooc_cmd_area_visible',
    'ooc_cmd_getarea',
    'ooc_cmd_getareas',
    'ooc_cmd_gethubs',
    'ooc_cmd_gethubslist',
    'ooc_cmd_getafk',
    'ooc_cmd_invite',
    'ooc_cmd_uninvite',
    'ooc_cmd_area_kick',
    'ooc_cmd_pos_lock',
    'ooc_cmd_pos_lock_clear',
    'ooc_cmd_knock',
    'ooc_cmd_peek',
    'ooc_cmd_max_players',
    'ooc_cmd_desc',
    'ooc_cmd_edit_ambience',
    'ooc_cmd_lights',
]


def ooc_cmd_bg(client, arg, BS = True):
    """
    Imposta lo sfondo di un'area.
    Se non viene selezionato nessun bg, verrà mostrato il bg attuale impostato nell'area.
    Uso: /bg <background>
    """
    if len(arg) == 0:
        pos_lock = ''
        if len(client.area.pos_lock) > 0:
            pos = ', '.join(str(l) for l in client.area.pos_lock)
            pos_lock = f'\nAvailable positions: {pos}.'
        client.send_ooc(f'Current background is {client.area.background}.{pos_lock}')
        return
    if not client in client.area.owners and not client.is_mod and client.area.bg_lock:
        raise AreaError("This area's background is locked!")
    if client.area.cannot_ic_interact(client):
        raise AreaError("You are not on the area's invite list!")
    if not client.is_mod and not (client in client.area.owners) and client.char_id == -1:
        raise ClientError("You may not do that while spectating!")
    if client.area.dark and not client.is_mod and not (client in client.area.owners):
        raise ClientError('You must be authorized to do that.')
    try:
        client.area.change_background(arg)
    except AreaError:
        raise
    if BS:
     client.area.broadcast_ooc(
        f'{client.showname} changed the background to {arg}.')
    database.log_area('bg', client, client.area, message=arg)


def ooc_cmd_bgs(client, arg):
    """
    Mostra gli sfondi disponibili del server.
    Uso: /bgs
    """
    f = open('config/backgrounds.yaml', 'r')
    lines = f.readlines()
    if arg == "":
     msg = '\n CATEGORIE BG:\n'
     for line in lines:
       if line.split('-')[0] == "":
         msg += f'\n  {line.split(":")[0]}'
     client.send_ooc(f'{msg}')
    else:
     index = -1
     i = -1
     for line in lines:
       index = index+1
       if line.split('- ')[1].split(':')[0].lower() == f'{arg}'.lower():
        i = index+1
     categoria = lines[i].split("- ")[1].split(":")[0].split("\n")[0]
     msg = f'\n Categoria {categoria}: \n\n' 
     if not i == -1:
      f = 0
      while f == 0:
       msg += f' {lines[i]}'
       i = i+1
       if i == len(lines) or ':' in lines[i]:
        f = -1
      client.send_ooc(f'{msg}')
     else:
      client.send_ooc('Categoria non trovata')
        
       

def ooc_cmd_status(client, arg):
    """
    Show or modify the current status of an area.
    Usage: /status <idle|rp|casing|looking-for-players|lfp|recess|gaming>
    """
    if not client.area.area_manager.arup_enabled:
        raise AreaError('This hub does not use the /status system.')
    if len(arg) == 0:
        client.send_ooc(f'Current status: {client.area.status}')
    else:
        if not client.area.can_change_status and not client.is_mod and not client in client.area.owners:
            raise AreaError("This area's status cannot be changed by anyone who's not a CM or mod!")
        if client.area.cannot_ic_interact(client):
            raise AreaError("You are not on the area's invite list!")
        if not client.is_mod and not (client in client.area.owners) and client.char_id == -1:
            raise ClientError("You may not do that while spectating!")
        try:
            client.area.change_status(arg)
            client.area.broadcast_ooc('{} changed status to {}.'.format(
                client.showname, client.area.status))
            database.log_area('status', client, client.area, message=arg)
        except AreaError:
            raise


def ooc_cmd_area(client, arg):
    """
    Mostra la lista delle aree, o ti fa muovere verso una a scelta.
    Uso: /area [id] or /area [name]
    """
    if arg == '':
        client.send_area_list(full=client.is_mod or client in client.area.owners)
        return

    try:
        for area in client.area.area_manager.areas:
            a = arg.split(' ')[0]
            aid = a.strip('[]')
            if (a.startswith('[') and a.endswith(']') and aid.isdigit() and area.id == int(aid)) or area.name.lower() == arg.lower() or area.abbreviation == arg or (arg.isdigit() and area.id == int(arg)):
                client.change_area(area)
                return
        raise AreaError('Targeted area not found!')
    except ValueError:
        raise ArgumentError('Area ID must be a name, abbreviation or a number.')
    except (AreaError, ClientError):
        raise


def ooc_cmd_area_visible(client, arg):
    """
    Mostra solo le aree non collegate e non nascoste. Utili per i GM.
    Uso: /area_visible
    """
    if arg != '':
        raise ArgumentError('This command takes no arguments!')
    client.send_area_list(full=False)


def ooc_cmd_getarea(client, arg):
    """
    Fornisce informazioni riguardo l'area in cui ti trovi.
    Uso: /getarea
    """
    if not client.is_mod and not (client in client.area.owners):
        if client.blinded:
            raise ClientError('You are blinded!')
        if not client.area.can_getarea:
            raise ClientError('You cannot use /getarea in this area!')
        if client.area.dark:
            raise ClientError('This area is shrouded in darkness!')
    client.send_area_info(client.area.id, False)


      
  
def ooc_cmd_getareas(client, arg):
    """
    Fornisce informazioni riguardo tutte le aree dell'hub in cui ti trovi.
    Uso: /getareas
    """
    if not client.is_mod and not (client in client.area.area_manager.owners) and client.char_id != -1:
        if client.blinded:
            raise ClientError('You are blinded!')
        if not client.area.area_manager.can_getareas:
            raise ClientError('You cannot use /getareas in this hub!')
    client.send_area_info(-1, False)


def ooc_cmd_getafk(client, arg):
    """
    Mostra tutti i giocatori AFK nell'area in cui ti trovi o in tutte le aree.
    Uso: /getafk [all]
    """
    if arg == 'all':
        arg = -1
    elif len(arg) == 0:
        arg = client.area.id
    else:
        raise ArgumentError('There is only one optional argument [all].')
    client.send_area_info(arg, False, afk_check=True)


@mod_only(area_owners=True)
def ooc_cmd_invite(client, arg):
    """
    Permette di far accedere uno specifico utente in un'area lockata o di farlo parlare in un'area spectabile.
    l'ID può essere * per invitare tutti nell'area corrente.
    Uso: /invite <id>
    """
    if not arg:
        msg = 'Current invite list:\n'
        msg += '\n'.join([f'[{c.id}] {c.showname}' for c in client.server.client_manager.clients if c.id in client.area.invite_list])
        msg += '\nUse /invite <id> to invite someone.'
        client.send_ooc(msg)
        return

    args = arg.split(' ')

    try:
        if args[0] == '*':
            targets = [c for c in client.area.clients if c != client and c != client.area.owners]
        else:
            targets = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(args[0]), False)
    except ValueError:
        raise ArgumentError('Area ID must be a number or *.')

    try:
        for c in targets:
            client.area.invite_list.add(c.id)
            client.send_ooc(f'{c.showname} is invited to your area.')
            c.send_ooc(
                f'You were invited and given access to {client.area.name}.')
            database.log_area('invite', client, client.area, target=c)
    except:
        raise ClientError('You must specify a target. Use /invite <id>')


@mod_only(area_owners=True)
def ooc_cmd_uninvite(client, arg):
    """
    Revoca i permessi dati ad un giocatore invitato.
    l'ID può essere * per revocare tutti i permessi dati a tutti gli utenti nell'area corrente.
    Uso: /uninvite <id>
    """
    if not arg:
        raise ClientError('You must specify a target. Use /uninvite <id>')
    args = arg.split(' ')
    try:
        if args[0] == '*':
            targets = [c for c in client.area.clients if c != client and c != client.area.owners]
        else:
            targets = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(args[0]), False)
    except ValueError:
        raise ArgumentError('Area ID must be a number or *.')

    if targets:
        try:
            for c in targets:
                client.send_ooc(
                    "You have removed {} from the whitelist.".format(
                        c.showname))
                c.send_ooc(
                    "You were removed from the area whitelist.")
                database.log_area('uninvite', client, client.area, target=c)
                client.area.invite_list.discard(c.id)
        except AreaError:
            raise
        except ClientError:
            raise
    else:
        client.send_ooc("No targets found.")


@mod_only(area_owners=True)
def ooc_cmd_area_kick(client, arg):
    """
    Rimuove un giocatore dall'area corrente e li sposta in un'area diversa.
    Se l'id è * , rimuoverà tutti tranne l'utilizzatore e i CM presenti.
    Se la destinazione non è specificata, la destinazio di base è l'area con id 0.
    target_pos è la posizione opzionale dove tutti dovrebbero andare quando kickati.
    Uso: /area_kick <id> [destination] [target_pos]]
    """
    if not arg:
        raise ClientError(
            'You must specify a target. Use /area_kick <id> [destination #] [target_pos]')

    args = arg.split(' ')
    try:
        if args[0] == 'afk':
            targets = client.server.client_manager.get_targets(client, TargetType.AFK,
                                                            args[0], False)
        elif args[0] == '*':
            targets = [c for c in client.area.clients if c != client and c != client.area.owners]
        else:
            targets = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(args[0]), False)
    except ValueError:
        raise ArgumentError('Area ID must be a number, afk or *.')

    if targets:
        try:
            for c in targets:
                # We're a puny CM, we can't do this.
                if not client.is_mod and not client in client.area.area_manager.owners and not c in client.area.clients:
                    raise ArgumentError("You can't kick someone from another area as a CM!")
                if len(args) == 1:
                    area = client.area.area_manager.default_area()
                    output = area.id
                else:
                    try:
                        area = client.area.area_manager.get_area_by_id(
                            int(args[1]))
                        output = args[1]
                    except AreaError:
                        raise
                    if not client.is_mod and not client in client.area.area_manager.owners and not client in area.owners:
                        raise ArgumentError("You can't kick someone to an area you don't own as a CM!")
                target_pos = ''
                old_area = c.area
                if len(args) >= 3:
                    target_pos = args[2]
                client.send_ooc(
                    f'Attempting to kick [{c.id}] {c.showname} from [{old_area.id}] {old_area.name} to [{area.id}] {area.name}.')
                c.set_area(area, target_pos)
                c.send_ooc(
                    f"You were kicked from [{old_area.id}] {old_area.name} to [{area.id}] {area.name}.")
                database.log_area('area_kick', client, client.area, target=c, message=output)
                client.area.invite_list.discard(c.id)
        except ValueError:
            raise ArgumentError('Area ID must be a number.')
        except AreaError:
            raise
        except ClientError:
            raise
    else:
        client.send_ooc("No targets found.")


def ooc_cmd_pos_lock(client, arg):
    """
    Blocca le posizioni disponibili dell'area corrente con una lista di posizioni separate da uno spazio.
    Usa /pos_lock_clear per rendere la lista vuota.
    Se la tua pos contiene degli spazi, allora deve essere in un elenco separato da virgole come /pos_lock pos uno, pos due, pos X
    Se sei bloccato in una singola pos contenente spazi, terminalo con una virgola come /pos_lock questa è una pos,
    Uso:  /pos_lock <pos(s)>
    """
    if client.area.dark:
        if not arg or arg.strip() == '':
            pos = client.area.pos_dark
            client.send_ooc(f'Current darkness pos is {pos}.')
            return
        if not client.is_mod and not (client in client.area.owners):
            raise ClientError('You must be authorized to do that.')
        client.area.pos_dark = arg
        client.area.broadcast_ooc(f'Locked darkness pos into {arg}.')
        return
    if not arg or arg.strip() == '':
        if len(client.area.pos_lock) > 0:
            pos = ', '.join(str(l) for l in client.area.pos_lock)
            client.send_ooc(f'Pos_lock is currently {pos}.')
        else:
            client.send_ooc('No pos lock set.')
        return

    if arg.strip().lower() == 'none':
        ooc_cmd_pos_lock_clear(client, arg)
        return

    if not client.is_mod and not (client in client.area.owners):
        raise ClientError('You must be authorized to do that.')

    client.area.pos_lock.clear()
    if ',' in arg:
        args = arg.split(',')
    else:
        args = arg.split()
    args = sorted(set(args),key=args.index) #remove duplicates while preserving order
    for pos in args:
        pos = pos.strip().lower()
        if pos == 'none' or pos == '':
            continue
        client.area.pos_lock.append(pos)

    pos = ', '.join(str(l) for l in client.area.pos_lock)
    client.area.broadcast_ooc(f'Locked pos into {pos}.')
    client.area.send_command('SD', '*'.join(client.area.pos_lock)) #set that juicy pos dropdown


@mod_only(area_owners=True)
def ooc_cmd_pos_lock_clear(client, arg):
    """
    Elimina il blocco delle posizioni rendendole nuovamente tutte disponibili.
    Uso:  /pos_lock_clear
    """
    client.area.pos_lock.clear()
    client.area.broadcast_ooc('Position lock cleared.')


def ooc_cmd_knock(client, arg):
    """
    Bussa in un'area a tua scelta per richiamare l'attenzione nell'area.
    Uso:  /knock <id>
    """
    if arg == '':
        raise ArgumentError('Failed to knock: you need to input an accessible area name or ID to knock!')
    if client.blinded:
        raise ClientError('Failed to knock: you are blinded!')
    try:
        area = None
        for _area in client.area.area_manager.areas:
            if _area.name.lower() == arg.lower() or _area.abbreviation == arg or (arg.isdigit() and _area.id == int(arg)):
                area = _area
                break
        if area == None:
            raise ClientError('Target area not found.')
        if area == client.area:
            client.area.broadcast_ooc(f'[{client.id}] {client.showname} knocks for attention.')
            return

        allowed = client.is_mod or client in area.owners or client in client.area.owners
        if not allowed:
            if len(client.area.links) > 0:
                if not str(area.id) in client.area.links:
                    raise ClientError(f'Failed to knock on [{area.id}] {area.name}: That area is inaccessible!')

                if str(area.id) in client.area.links:
                    # Get that link reference
                    link = client.area.links[str(area.id)]

                    # Link requires us to be inside a piece of evidence
                    if len(link["evidence"]) > 0 and not (client.hidden_in in link["evidence"]):
                        raise ClientError(f'Failed to knock on [{area.id}] {area.name}: That area is inaccessible!')
            if client.area.locked and not client.id in client.area.invite_list:
                raise ClientError(f'Failed to knock on [{area.id}] {area.name}: Current area is locked!')

        client.area.broadcast_ooc(f'[{client.id}] {client.showname} knocks on [{area.id}] {area.name}.')
        area.broadcast_ooc(f'!! Someone is knocking from [{client.area.id}] {client.area.name} !!')
    except ValueError:
        raise ArgumentError('Failed to knock: you need to input an accessible area name or ID to knock!')
    except (AreaError, ClientError):
        raise


def ooc_cmd_peek(client, arg):
    """
    Sbircia in un'area per vedere se ci sono persone al suo interno.
    Uso:  /peek <id>
    """
    if arg == '':
        raise ArgumentError('You need to input an accessible area name or ID to peek into it!')
    if client.blinded:
        raise ClientError('You are blinded!')
    try:
        area = None
        for _area in client.area.area_manager.areas:
            if _area.name.lower() == arg.lower() or _area.abbreviation == arg or (arg.isdigit() and _area.id == int(arg)):
                area = _area
                break
        if area == None:
            raise ClientError('Target area not found.')
        if area == client.area:
            ooc_cmd_getarea(client, '')
            return

        try:
            client.try_access_area(area)
            if not area.can_getarea:
                raise ClientError("Can't peek in that area!")
            if area.dark:
                raise ClientError('Area is dark!')
        except ClientError as ex:
            if not client.area.dark and not client.sneaking and not client.hidden and 'locked' in str(ex).lower():
                client.area.broadcast_ooc(f'[{client.id}] {client.showname} tried to peek into [{area.id}] {area.name} but {str(ex).lower()}')
                # People from within the area have no distinction between peeking and moving inside
                area.broadcast_ooc(f'Someone tried to enter from [{client.area.id}] {client.area.name} but {str(ex).lower()}')
            client.send_ooc(f'Failed to peek into [{area.id}] {area.name}: {ex}')
            return
        else:
            sorted_clients = []
            for c in area.clients:
                if not c.hidden and not c in area.owners and not c.is_mod: #pure IC
                    sorted_clients.append(c)

            _sort = [c.showname for c in sorted(sorted_clients, key=lambda x: x.showname)]

            # this would be nice to be a separate "make human readable list" func
            if len(_sort) == 2:
                sorted_clients = ' and '.join(_sort)
            elif len(_sort) > 2:
                sorted_clients = ', '.join(_sort[:-1])
                sorted_clients = "{} and {}".format(sorted_clients, _sort[-1])
            elif len(_sort) == 1:
                sorted_clients = _sort[0]

            if len(sorted_clients) <= 0:
                sorted_clients = 'nobody'

            if not client.sneaking and not client.hidden:
                client.area.broadcast_ooc(f'[{client.id}] {client.showname} peeks into [{area.id}] {area.name}...')
            else:
                client.send_ooc(f'You silently peek into [{area.id}] {area.name}...')
            client.send_ooc(f'There\'s {sorted_clients}.')
    except ValueError:
        raise ArgumentError('Failed to peek: you need to input an accessible area name or ID to knock!')
    except (AreaError, ClientError):
        raise


@mod_only(area_owners=True)
def ooc_cmd_max_players(client, arg):
    """
    Imposta un limite massimo di utenti per l'area in cui ti trovi (può variare tra -1 e 99).
    Uso: /max_players [num]
    """
    if arg == '':
        client.send_ooc(f'Max amount of players for the area is {client.area.max_players}.')
        return

    try:
        arg = int(arg)
        if arg < -1 or arg > 99:
            raise ClientError('The min-max values are -1 and 99!')
        client.area.max_players = arg
        client.send_ooc(f'New max amount of players for the area is now {client.area.max_players}.')
    except ValueError:
        raise ArgumentError('Area ID must be a name, abbreviation or a number.')
    except (AreaError, ClientError):
        raise


def ooc_cmd_desc(client, arg):
    """
    Imposta una descrizione dell'area che appare agli utenti ogni volta che accedono in quell'area.
    Uso: /desc [desc]
    """
    if client.blinded:
        raise ClientError('You are blinded!')
    if len(arg) == 0:
        desc = client.area.desc
        if client.area.dark:
            desc = client.area.desc_dark
        client.send_ooc(f'Description: {desc}')
        database.log_area('desc.request', client, client.area)
    else:
        if client.area.cannot_ic_interact(client):
            raise ClientError("You are not on the area's invite list!")
        if not client.is_mod and not (client in client.area.owners) and client.char_id == -1:
            raise ClientError("You may not do that while spectating!")
        if client.area.dark:
            if not client.is_mod and not (client in client.area.owners):
                raise ClientError('You must be authorized to do that.')
            client.area.desc_dark = arg.strip()
        else:
            client.area.desc = arg.strip()
        desc = arg[:128]
        if len(arg) > len(desc):
            desc += "... Use /desc to read the rest."
        client.area.broadcast_ooc(f'{client.showname} changed the area description to: {desc}.')
        database.log_area('desc.change', client, client.area, message=arg)


@mod_only(area_owners=True)
def ooc_cmd_edit_ambience(client, arg):
    """
    Attiva la modalità editor per le impostazioni dell'ambiente. Riprodurre una musica lo imposterà come ambiente dell'area.
    tog può essere settato su `on`, `off` or empty (acceso, spento o vuoto).
    Uso: /edit_ambience [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError("This command can only take one argument ('on' or 'off') or no arguments at all!")
    if arg:
        if arg == 'on':
            client.edit_ambience = True
        elif arg == 'off':
            client.edit_ambience = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.edit_ambience = not client.edit_ambience
    stat = 'no longer'
    if client.edit_ambience:
        stat = 'now'
    client.send_ooc(f'Playing a song will {stat} edit the area\'s ambience.')


@mod_only(area_owners=True)
def ooc_cmd_lights(client, arg):
    """
    Accende/spegne le luci per l'area in cui ti trovi. Se le luci sono spente, gli utenti non saranno in grado di usare /getarea o vedere le prove.
    Gli utenti, inoltre, non saranno in grado di vedere gli spostamenti tra aree o usare /charesc.
    Puoi cambiare /bg, /desc e /pos_lock dell'area quando è buia e verrannno reinseriti la prossima volta che l'area verrà resa nuovamente buia.
    tog può essere settato su `on`, `off` o empty (acceso, spento o vuoto).
    Usage: /lights [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError("This command can only take one argument ('on' or 'off') or no arguments at all!")
    if arg:
        if arg == 'on':
            client.area.dark = False
        elif arg == 'off':
            client.area.dark = True
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.area.dark = not client.area.dark
    stat = 'no longer'
    bg = client.area.background
    if client.area.dark:
        stat = 'now'
        bg = client.area.background_dark
    for c in client.area.clients:
        pos = c.pos
        if c.area.dark:
            pos = client.area.pos_dark
        c.send_command('BN', bg, pos)
    client.send_ooc(f'This area is {stat} dark.')

def ooc_cmd_gethubslist(client, arg):
   """
   Mostra una lista di tutte le hub.
   Uso: /gethubslist
   """
   client.send_hub_area_list(False)

def ooc_cmd_gethubs(client, arg):
    """
    Fornisce informazioni riguardo tutte le hub.
    Uso: /gethubs
    """
    if not client.is_mod and not (client in client.area.area_manager.owners) and client.char_id != -1:
        if client.blinded:
            raise ClientError('You are blinded!')
        if not client.area.area_manager.can_getareas:
            raise ClientError('You cannot use /getareas in this hub!')
    client.send_hub_area_info(-1, False)