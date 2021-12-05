import random

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only

__all__ = [
    'ooc_cmd_switch',
    'ooc_cmd_pos',
    'ooc_cmd_forcepos',
    'ooc_cmd_charselect',
    'ooc_cmd_randomchar',
    'ooc_cmd_charcurse',
    'ooc_cmd_uncharcurse',
    'ooc_cmd_charids',
    'ooc_cmd_reload',
    'ooc_cmd_blind',
    'ooc_cmd_unblind',
    'ooc_cmd_player_move_delay',
    'ooc_cmd_hide',
    'ooc_cmd_unhide',
    'ooc_cmd_sneak',
    'ooc_cmd_unsneak',
    'ooc_cmd_listen_pos',
    'ooc_cmd_unlisten_pos',
    'ooc_cmd_save_character_data',
    'ooc_cmd_load_character_data',
    'ooc_cmd_keys_set',
    'ooc_cmd_keys_add',
    'ooc_cmd_keys_remove',
    'ooc_cmd_keys',
    'ooc_cmd_kms',
    'ooc_cmd_chardesc',
    'ooc_cmd_chardesc_set',
    'ooc_cmd_chardesc_get',
    'ooc_cmd_narrate',
    'ooc_cmd_blankpost',
    'ooc_cmd_firstperson',
]


def ooc_cmd_switch(client, arg):
    """
    Cambia il personaggio. Se un moderatore utilizza il comando e il personaggio è già preso,
    all'utente che possiede quel personaggio ne verrà assegnato uno casualmente.
    Uso: /switch <name>
    """
    if len(arg) == 0:
        raise ArgumentError('You must specify a character name.')
    try:
        # loser wants to spectate
        if arg == '-1' or arg.lower() == 'spectator':
            cid = -1
        elif not arg.isnumeric():
            cid = client.server.get_char_id_by_name(arg)
        else:
            cid = int(arg)
    except ServerError:
        raise
    try:
        client.change_character(cid, client.is_mod or client in client.area.owners)
    except ClientError:
        raise
    client.send_ooc('Character changed.')


def ooc_cmd_pos(client, arg, BS = True):
    """
    Imposta la posizione del tuo personaggio nell'area corrente.
    Uso: /pos <name>
    """
    if len(arg) == 0:
        client.send_ooc(f'Your current position is {client.pos}.')
    else:
        try:
            client.change_position(arg)
        except ClientError:
            raise
        client.area.broadcast_evidence_list()
        if BS:
         client.send_ooc('Position changed.')


@mod_only(area_owners=True)
def ooc_cmd_forcepos(client, arg):
    """
    Imposta la posizione di un utente nell'area corrente.
    Uso: /forcepos <pos> <target>
    """
    args = arg.split()

    if len(args) < 1:
        raise ArgumentError(
            'Not enough arguments. Use /forcepos <pos> <target>. Target should be ID, OOC-name or char-name. Use /getarea for getting info like "[ID] char-name".'
        )

    targets = []

    pos = args[0]
    if len(args) > 1:
        targets = client.server.client_manager.get_targets(
            client, TargetType.CHAR_NAME, " ".join(args[1:]), True)
        if len(targets) == 0 and args[1].isdigit():
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(args[1]), True)
        if len(targets) == 0:
            targets = client.server.client_manager.get_targets(
                client, TargetType.OOC_NAME, " ".join(args[1:]), True)
        if len(targets) == 0:
            raise ArgumentError('No targets found.')
    else:
        for c in client.area.clients:
            targets.append(c)

    for t in targets:
        try:
            t.change_position(pos)
            t.area.broadcast_evidence_list()
            t.send_ooc(f'Forced into /pos {pos}.')
            database.log_area('forcepos', client, client.area, target=t, message=pos)
        except ClientError:
            raise

    client.area.broadcast_ooc(
        '{} forced {} client(s) into /pos {}.'.format(client.showname,
                                                      len(targets), pos))


def ooc_cmd_charselect(client, arg):
    """
    Permette di andare nella selezione personaggio, o forzare un utente a cambiare personaggio.
    [char] forza l'utente ad usare uno specifico personaggio.
    Uso: /charselect [id] [char]
    """
    if not arg:
        client.char_select()
    else:
        args = arg.split()
        try:
            target = client.server.client_manager.get_targets(client, TargetType.ID,
                int(args[0]), False)[0]
            force_charselect(target, ' '.join(args[1:]))
        except Exception as ex:
            raise ArgumentError(f'Error encountered: {ex}. Use /charselect <target\'s id> [character]')


@mod_only(area_owners=True)
def force_charselect(client, char=''):
    if char != '':
        try:
            if char == '-1' or char.lower() == 'spectator':
                cid = -1
            elif not char.isnumeric():
                cid = client.server.get_char_id_by_name(char)
            else:
                cid = int(char)
        except ServerError:
            raise
        try:
            client.change_character(cid, True)
        except ClientError:
            raise
    else:
        client.char_select()


def ooc_cmd_randomchar(client, arg):
    """
    Seleziona un personaggio casuale.
    Uso: /randomchar
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if len(client.charcurse) > 0:
        free_id = random.choice(client.charcurse)
    else:
        try:
            free_id = client.area.get_rand_avail_char_id()
        except AreaError:
            raise
    try:
        client.change_character(free_id)
    except ClientError:
        raise
    client.send_ooc('Randomly switched to {}'.format(
        client.char_name))


@mod_only()
def ooc_cmd_charcurse(client, arg):
    """
    Costringe un utente a scegliere in una lista limitata di personaggi.
    Uso: /charcurse <id> [charids...]
    """
    if len(arg) == 0:
        raise ArgumentError(
            'You must specify a target (an ID) and at least one character ID. Consult /charids for the character IDs.'
        )
    elif len(arg) == 1:
        raise ArgumentError(
            'You must specific at least one character ID. Consult /charids for the character IDs.'
        )
    args = arg.split()
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(args[0]), False)
    except:
        raise ArgumentError(
            'You must specify a valid target! Make sure it is a valid ID.')
    if targets:
        for c in targets:
            log_msg = ''
            part_msg = ' [' + str(c.id) + '] to'
            for raw_cid in args[1:]:
                try:
                    cid = int(raw_cid)
                    c.charcurse.append(cid)
                    part_msg += ' ' + str(client.server.char_list[cid]) + ','
                    log_msg += ' ' + str(client.server.char_list[cid]) + ','
                except:
                    ArgumentError('' + str(raw_cid) +
                                  ' does not look like a valid character ID.')
            part_msg = part_msg[:-1]
            part_msg += '.'
            log_msg = log_msg[:-1]
            c.char_select()
            database.log_area('charcurse', client, client.area, target=c, message=log_msg)
            client.send_ooc('Charcursed' + part_msg)
    else:
        client.send_ooc('No targets found.')


@mod_only()
def ooc_cmd_uncharcurse(client, arg):
    """
    Rimuove la restrizione dei personaggi limitati ad un utente.
    Uso: /uncharcurse <id>
    """
    if len(arg) == 0:
        raise ArgumentError('You must specify a target (an ID).')
    args = arg.split()
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(args[0]), False)
    except:
        raise ArgumentError(
            'You must specify a valid target! Make sure it is a valid ID.')
    if targets:
        for c in targets:
            if len(c.charcurse) > 0:
                c.charcurse = []
                database.log_area('uncharcurse', client, client.area, target=c)
                client.send_ooc(f'Uncharcursed [{c.id}].')
                c.char_select()
            else:
                client.send_ooc(f'[{c.id}] is not charcursed.')
    else:
        client.send_ooc('No targets found.')


@mod_only()
def ooc_cmd_charids(client, arg):
    """
    Mostra gli ID dei personaggi.
    Uso: /charids
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    msg = 'Here is a list of all available characters on the server:'
    for c in range(0, len(client.server.char_list)):
        msg += '\n[' + str(c) + '] ' + client.server.char_list[c]
    client.send_ooc(msg)


def ooc_cmd_reload(client, arg):
    """
    Ricarica un personaggio nella sua posizione e sprite iniziale.
    Uso: /reload
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    try:
        client.reload_character()
    except ClientError:
        raise
    client.send_ooc('Character reloaded.')


@mod_only(hub_owners=True)
def ooc_cmd_blind(client, arg):
    """
    Impedisce ad un utente di vedere chi parla o di parlare nella IC.
    Uso: /blind <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        targets = []
        ids = [int(s) for s in arg.split(' ')]
        for targ_id in ids:
            c = client.server.client_manager.get_targets(client, TargetType.ID, targ_id, False)
            if c:
                targets = targets + c
    except:
        raise ArgumentError('You must specify a target. Use /blind <id>.')

    if targets:
        for c in targets:
            if c.blinded:
                client.send_ooc(f'Client [{c.id}] {c.name} already blinded!')
                continue
            c.blind(True)
            client.send_ooc(f'You have blinded [{c.id}] {c.name} from using /getarea and seeing non-broadcasted IC messages.')
    else:
        raise ArgumentError('No targets found.')


@mod_only(hub_owners=True)
def ooc_cmd_unblind(client, arg):
    """
    Rimuove gli effetti del comando /blind.
    Uso: /unblind <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        targets = []
        ids = [int(s) for s in arg.split(' ')]
        for targ_id in ids:
            c = client.server.client_manager.get_targets(client, TargetType.ID, targ_id, False)
            if c:
                targets = targets + c
    except:
        raise ArgumentError('You must specify a target. Use /unblind <id>.')

    if targets:
        for c in targets:
            if not c.blinded:
                client.send_ooc(f'Client [{c.id}] {c.name} already unblinded!')
                continue
            c.blind(False)
            client.send_ooc(f'You have unblinded [{c.id}] {c.name}.')
    else:
        raise ArgumentError('No targets found.')

@mod_only()
def ooc_cmd_player_move_delay(client, arg):
    """
    Setta il ritardo di spostamento di un utente in secondi. Può essere negativo.
    Il ritardo deve andare da -1800 a 1800 in secondi oppure si può lasciare vuoto per controllare.
    Uso: /player_move_delay <id> [delay]
    """
    args = arg.split()
    try:
        if len(args) > 0 and client in client.area.owners:
            c = client.server.client_manager.get_targets(client, TargetType.ID,
                                                        int(args[0]), False)[0]
            if len(args) > 1:
                move_delay = min(1800, max(-1800, int(args[1]))) # Move delay is limited between -1800 and 1800
                c.move_delay = move_delay
                client.send_ooc(f'Set move delay for {c.char_name} to {c.move_delay}.')
            else:
                client.send_ooc(f'Move delay for {c.char_name} is {c.move_delay}.')
        else:
            client.send_ooc(f'Your current move delay is {client.move_delay}.')
    except ValueError:
        raise ArgumentError('Delay must be an integer between -1800 and 1800.')
    except IndexError:
        raise ArgumentError('Target client not found. Use /player_move_delay <id> [delay].')
    except (AreaError, ClientError):
        raise


def ooc_cmd_hide(client, arg):
    """
    Nascondi una prova con il suo ID o nome.
    Uso: /hide <evi_name/id>
    """
    if arg == '':
        raise ArgumentError('Use /hide <evi_name/id> to hide in evidence, or /unhide to stop hiding.')
    try:
        if arg.isnumeric():
            arg = str(int(arg)-1)
        client.hide(True, arg)
        client.area.broadcast_area_list(client)
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


def ooc_cmd_unhide(client, arg):
    """
    Smette di nascondere una prova.
    Uso: /unhide
    """
    client.hide(False)
    client.area.broadcast_area_list(client)


def ooc_cmd_sneak(client, arg):
    """
    Permette di cambiare area senza essere annunciato in OOC.
    Uso: /sneak
    """
    if arg != '':
        raise ArgumentError('This command takes no arguments!')
    if client.sneaking:
        raise ClientError('You are already sneaking! Use /unsneak to stop sneaking.')
    client.sneak(True)


def ooc_cmd_unsneak(client, arg):
    """
    Smette di cambiare area senza essere annunciato in OOC.
    Uso: /sneak
    """
    if arg != '':
        raise ArgumentError('This command takes no arguments!')
    if not client.sneaking:
        raise ClientError('You are not sneaking! Use /sneak to start sneaking.')
    client.sneak(False)


def ooc_cmd_listen_pos(client, arg):
    """
    Leggi soltanto i messaggi della IC provenienti dalla stessa posizione in cui ti trovi o che vuoi visualizzare.
    Tutti i messaggi provenienti da altre posizioni verranno visualizzate in OOC.
    Uso: /listen_pos [pos(s)]
    """
    args = arg.split()
    value = 'self'
    if len(args) > 0:
        value = args

    client.listen_pos = value
    if value == 'self':
        value = f'listening to your own pos {client.pos}'
    else:
        value = ', '.join(value)
        value = f'listening to pos {value}'
    client.send_ooc(f'You are {value}. Use /unlisten_pos to stop listening.')


def ooc_cmd_unlisten_pos(client, arg):
    """
    Rimuove gli effetti del comando /listen_pos.
    Uso: /unlisten_pos
    """
    if client.listen_pos == None:
        raise ClientError('You are not listening to any pos at the moment!')
    client.listen_pos = None
    client.send_ooc(f'You re no longer listening to any pos (All IC messages will appear as normal).')


@mod_only(hub_owners=True)
def ooc_cmd_save_character_data(client, arg):
    """
    Salva il ritardo, e altre informazioni per un personaggio.
    Uso: /save_character_data <path>
    """
    if len(arg) < 3:
        client.send_ooc("Filename must be at least 3 symbols long!")
        return

    try:
        path = 'storage/character_data'
        arg = f'{path}/{arg}.yaml'
        client.area.area_manager.save_character_data(arg)
        client.send_ooc(f'Saving as {arg} character data...')
    except AreaError:
        raise


@mod_only(hub_owners=True)
def ooc_cmd_load_character_data(client, arg):
    """
    Carica il ritardo e altre informazioni per un personaggio.
    Uso: /load_character_data <path>
    """
    try:
        path = 'storage/character_data'
        arg = f'{path}/{arg}.yaml'
        client.area.area_manager.load_character_data(arg)
        client.send_ooc(f'Loading {arg} character data...')
    except AreaError:
        raise


def mod_keys(client, arg, mod=0):
    """
    A helper function to reduce copy-pasted code for /keys_(set|add|remove) commands.
    Modifies the keys of the target client/character folder/character id.
    :param arg: The arguments passed from the /keys_(set|add|remove) commands.
    :param mod: A number from 0-2 that dictates the operation. 0 = set, 1 = add, 2 = remove.
    """
    args = arg.split()
    if len(args) <= 1 and mod != 0:
        raise ArgumentError("Please provide the key(s) to set. Keys must be a number 5 or a link eg. 1-5.")
    try:
        if args[0].isnumeric():
            target = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), False)
            if target:
                target = target[0].char_id
            else:
                if args[0] != '-1' and (int(args[0]) in client.server.char_list):
                    target = int(args[0])
        else:
            try:
                target = client.server.get_char_id_by_name(arg)
            except (ServerError):
                raise

        if len(args) > 1:
            args = args[1:]
        else:
            args = []
        keys = []

        if mod == 1:
            keys = client.area.area_manager.get_character_data(target, 'keys', [])
        for a in args:
            for key in a.split('-'):
                # make sure all the keys are integers
                key = int(key)
            if not (a in keys):
                if mod == 2:
                    keys.remove(a)
                else:
                    keys.append(a)
        client.area.area_manager.set_character_data(target, 'keys', keys)
        client.send_ooc(f'Character folder {client.server.char_list[target]}\'s keys are updated: {keys}')
    except ValueError:
        raise ArgumentError('Keys must be a number like 5 or a link eg. 1-5.')
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_keys_set(client, arg):
    """
    Imposta le chiavi di un client/cartella di un personaggio/ID di un personaggio. Le chiavi devono essere un numero come 5 o compreso come 1-5.
    Uso: /keys_set <char> [key(s)]
    """
    if not arg:
        raise ArgumentError("Usage: /keys_set <char> [key(s)].")

    mod_keys(client, arg)


@mod_only(hub_owners=True)
def ooc_cmd_keys_add(client, arg):
    """
    Aggiunge le chiavi di un client/cartella di un personaggio/ID di un personaggio. Le chiavi devono essere un numero come 5 o compreso come 1-5.
    Uso: /keys_add <char> [key(s)]
    """
    if not arg:
        raise ArgumentError("Usage: /keys_add <char> [key(s)].")

    mod_keys(client, arg, 1)


@mod_only(hub_owners=True)
def ooc_cmd_keys_remove(client, arg):
    """
    Rimuove le chiavi di un client/cartella di un personaggio/ ID di un personaggio. Le chiavi devono essere un numero come 5 o compreso come 1-5.
    Uso: /keys_remove <char> [key(s)]
    """
    if not arg:
        raise ArgumentError("Usage: /keys_remove <char> [area id(s)]. Removes the selected 'keys' from the user.")

    mod_keys(client, arg, 2)


def ooc_cmd_keys(client, arg):
    """
    Controlla le tue chiavi o di qualcun altro (se sei mod).
    Le chiavi ti permettono di lockare (/lock) o unlockare (/unlock) specifiche o aree collegate se scritte come 1-5.
    Uso: /keys [target_id]
    """
    args = arg.split()
    if len(args) < 1:
        client.send_ooc(f'Your current keys are {client.keys}')
        return
    if not client.is_mod and not (client in client.area.area_manager.owners):
        raise ClientError('Only mods and GMs can check other people\'s keys.')
    if len(args) == 1:
        try:
            if args[0].isnumeric():
                target = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), False)
                if target:
                    target = target[0].char_id
                else:
                    if args[0] != '-1' and (int(args[0]) in client.server.char_list):
                        target = int(args[0])
            else:
                try:
                    target = client.server.get_char_id_by_name(arg)
                except (ServerError):
                    raise
            keys = client.area.area_manager.get_character_data(target, 'keys', [])
            client.send_ooc(f'{client.server.char_list[target]} current keys are {keys}')
        except:
            raise ArgumentError('Target not found.')
    else:
        raise ArgumentError("Usage: /keys [target_id].")


def ooc_cmd_kms(client, arg):
    """
    Sta per Kick MySelf - Kicka tutti gli altri client aperti da te.
    Utile se sei stato disconnesso e il tuo vecchio client non è ancora scomparso.
    Uso: /kms
    """
    if arg != '':
        raise ArgumentError('This command takes no arguments!')
    for target in client.server.client_manager.get_multiclients(client.ipid, client.hdid):
        if target != client:
            target.disconnect()
    client.send_ooc('Kicked other instances of client.')
    database.log_misc('kms', client)


def ooc_cmd_chardesc(client, arg):
    """
    Mostra la descrizione del tuo personaggio se non richiedi personaggi specifici.
    Guarda alle descrizioni del personaggio di una persona solo se l'ID viene specificato.
    Inserisci la tua descrizione, se la descrizione è inserita al posto dell'ID.
    *La prima frase della tua descrizione viene mostrata nel messaggio del trasferimento tra aree!
    Per inserire la descrizione di qualcuno altro come moderatore/GM o semplicemente guardarle usa /chardesc_set o /chardesc_get.
    Uso: /chardesc [desc/id]
    """
    if len(arg) == 0:
        client.send_ooc(f'{client.char_name} Description: {client.desc}')
        database.log_area('chardesc.request', client, client.area)
        return

    if client.blinded:
        raise ClientError('You are blinded!')

    if client.area.dark:
        raise ClientError('This area is shrouded in darkness!')

    if arg.isnumeric():
        try:
            target = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), True)[0].char_id
            desc = client.area.area_manager.get_character_data(target, 'desc', '')
            target = client.server.char_list[target]
            client.send_ooc(f'{target} Description: {desc}')
            database.log_area('chardesc.request', client, client.area, message=target)
        except:
            raise ArgumentError('Target not found.')
    else:
        client.desc = arg
        if not client.hidden and not client.sneaking:
            desc = arg[:128]
            if len(arg) > len(desc):
                desc += "... Use /chardesc to read the rest."
            client.area.broadcast_ooc(f'{client.showname} changed their character description to: {desc}.')
        database.log_area('chardesc.change', client, client.area, message=arg)


@mod_only(hub_owners=True)
def ooc_cmd_chardesc_set(client, arg):
    """
    Imposta la descrizione di un personaggio usato da un utente, o la elimina.
    Uso: /chardesc_set <id> [desc]
    """
    args = arg.split(' ')
    if len(args) < 1:
        raise ArgumentError('Not enough arguments. Usage: /chardesc_set <id> [desc]')
    try:
        if args[0].isnumeric():
            target = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), False)
            if target:
                target = target[0].char_id
            else:
                if args[0] != '-1' and (int(args[0]) in client.server.char_list):
                    target = int(args[0])
        else:
            try:
                target = client.server.get_char_id_by_name(arg)
            except (ServerError):
                raise
        desc = ''
        if len(args) > 1:
            desc = ' '.join(args[1:])
        client.area.area_manager.set_character_data(target, 'desc', desc)
        target = client.server.char_list[target]
        client.send_ooc(f'{target} Description: {desc}')
        database.log_area('chardesc.set', client, client.area, message=f'{target}: {desc}')
    except:
        raise ArgumentError('Target not found.')


@mod_only(hub_owners=True)
def ooc_cmd_chardesc_get(client, arg):
    """
    Ottieni la descrizione del personaggio di qualcun altro.
    Uso: /chardesc_get <id>
    """
    try:
        if arg.isnumeric():
            target = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
            if target:
                target = target[0].char_id
            else:
                if arg != '-1' and (int(arg) in client.server.char_list):
                    target = int(arg)
        else:
            try:
                target = client.server.get_char_id_by_name(arg)
            except (ServerError):
                raise
        desc = client.area.area_manager.get_character_data(target, 'desc', '')
        target = client.server.char_list[target]
        client.send_ooc(f'{target} Description: {desc}')
        database.log_area('chardesc.get', client, client.area, message=f'{target}: {desc}')
    except:
        raise ArgumentError('Target not found.')


def ooc_cmd_narrate(client, arg):
    """
    Parla come un narratore nella tua prossima azione.
    tog può essere `on`, `off` or empty (acceso, spento o vuoto).
    Uso: /narrate [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError("This command can only take one argument ('on' or 'off') or no arguments at all!")
    if arg:
        if arg == 'on':
            client.narrator = True
        elif arg == 'off':
            client.narrator = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.narrator = not client.narrator
    if client.blankpost == True:
        client.blankpost = False
        client.send_ooc(f'You cannot be a narrator and blankposting at the same time. Blankposting disabled!')
    stat = 'no longer be narrating'
    if client.narrator:
        stat = 'be narrating now'
    client.send_ooc(f'You will {stat}.')


def ooc_cmd_blankpost(client, arg):
    """
    Permette di blankpostare usando un immagine all'interno di base/misc/blank.png. (Comparirà MissingNo se non è presente.)
    tog può essere `on`, `off` o empty (acceso, spento o vuoto).
    Usage: /blankpost [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError("This command can only take one argument ('on' or 'off') or no arguments at all!")
    if arg:
        if arg == 'on':
            client.blankpost = True
        elif arg == 'off':
            client.blankpost = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.blankpost = not client.blankpost
    if client.narrator == True:
        client.narrator = False
        client.send_ooc(f'You cannot be a narrator and blankposting at the same time. Narrating disabled!')
    stat = 'no longer be blankposting'
    if client.blankpost:
        stat = 'be blankposting now'
    client.send_ooc(f'You will {stat}.')


def ooc_cmd_firstperson(client, arg):
    """
    Parli come un narratore dalla tua prossima azione, ma solo per te stesso. Tutti gli altri vedranno la emote che hai usato.
    tog può essere `on`, `off` or empty (acceso, spento, o vuoto).
    Usage: /firstperson [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError("This command can only take one argument ('on' or 'off') or no arguments at all!")
    if arg:
        if arg == 'on':
            client.firstperson = True
        elif arg == 'off':
            client.firstperson = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.firstperson = not client.firstperson
    if client.narrator == True:
        client.narrator = False
        client.send_ooc(f'You cannot be a narrator and firstperson at the same time. Narrating disabled!')
    stat = 'no longer be firstperson'
    if client.firstperson:
        stat = 'be firstperson now'
    client.send_ooc(f'You will {stat}.')