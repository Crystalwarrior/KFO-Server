import re
import os
import shlex

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only
from server import evidence
from server import area
from .. import commands

__all__ = [
    'ooc_cmd_doc',
    'ooc_cmd_cleardoc',
    'ooc_cmd_case_list',
    'ooc_cmd_evidence_mod', # Not strictly casing - to be reorganized
    'ooc_cmd_evidence_swap', # Not strictly casing - to be reorganized
    'ooc_cmd_cm',
    'ooc_cmd_uncm',
    'ooc_cmd_setcase',
    'ooc_cmd_anncase',
    'ooc_cmd_blockwtce',
    'ooc_cmd_unblockwtce',
    'ooc_cmd_judgelog',
    'ooc_cmd_afk', # Not strictly casing - to be reorganized
    'ooc_cmd_remote_listen', # Not strictly casing - to be reorganized
    'ooc_cmd_testimony',
    'ooc_cmd_testimony_start',
    'ooc_cmd_testimony_clear',
    'ooc_cmd_testimony_remove',
    'ooc_cmd_testimony_amend',
    'ooc_cmd_testimony_swap',
    'ooc_cmd_cs',
    'ooc_cmd_pta',
    'ooc_cmd_concede',
    'ooc_cmd_sc',
    'ooc_cmd_lc',
    'ooc_cmd_cl',
    'ooc_cmd_dc',
]

@mod_only(area_owners=True)
def ooc_cmd_dc(client, arg):
    files = os.listdir('storage/cases')
    args = shlex.split(arg)
    if args[0].ini in files:
     f = open(f'storage/cases/{arg}.ini', 'r')
     lines = f.readlines()
     line = lines[1].split(' ')[3].split('"\n')[0]
     if args[1] == line:
      os.remove(f'storage/cases/{arg}.ini')
      client.send_ooc('Il caso è stato eliminato!')
     else:
      client.send_ooc('Hai sbagliato password!')
    else:
      client.send_ooc('Il nome del caso non è in lista')

def ooc_cmd_cl(client, arg):
    msg = '\nLista casi 📯:\n'
    files = os.listdir('storage\cases')
    for f in files:
     file = f[:-5]
     msg += f'\n- {file}'
    client.send_ooc(msg)

@mod_only(area_owners=True)
def ooc_cmd_sc(client, arg):
  if not arg == '':
    f = open(f'storage/cases/{arg}.yaml', 'w')
    f.write('[General]\n')
    f.write(f'author = "{client.name}"\n')
    f.write(f'doc = "{client.area.doc}"\n')
    f.write('status = "casing"\n\n\n')
    for evi in client.area.evi_list.evidences:
       f.write(f'[{client.area.evi_list.evidences.index(evi)}]\n')
       f.write(f'name={evi.name}\n')
       f.write(f'pos={evi.pos}\n')
       f.write(f'description={evi.desc}\n')
       f.write(f'image={evi.image}\n\n')
    client.send_ooc('Il caso è stato salvato!')
  else:
    client.send_ooc('Devi dare un nome al caso, per poterlo salvare')

@mod_only(area_owners=True)
def ooc_cmd_lc(client, arg):
   files = os.listdir('storage\cases')
   if f'{arg}.yaml' in files:
    f = open(f'storage/cases/{arg}.yaml', 'r')
    lines = f.readlines()
    line = shlex.split(lines[1])
    client.send_ooc(f'Questo caso è stato fatto da {line[2]}')
    line = shlex.split(lines[2])
    client.area.doc = line[2]
    commands.areas.ooc_cmd_status(client, 'casing')
    esci = -1
    i = -1
    while esci == -1:
      i = 0
      for line in lines:
       esci = 0
       if f'[{i}]' in line:
        esci = -1
        j = lines.index(line)
        name = lines[j+1].split('=')[1]
        desc = lines[j+3].split('=')[1]
        image = lines[j+4].split('=')[1]
        evidence.EvidenceList.add_evidence(client.area.evi_list, client, name, desc, image)
        area.Area.broadcast_evidence_list(client.area)
   else:
      client.send_ooc("Non c'è nessun caso con questo nome")
      

def ooc_cmd_doc(client, arg):
    """
    Mostra o cambia il link per il documento del caso.
    Uso: /doc [url]
    """
    if len(arg) == 0:
        client.send_ooc(f'Document: {client.area.doc}')
        database.log_area('doc.request', client, client.area)
    else:
        if client.area.cannot_ic_interact(client):
            raise ClientError("You are not on the area's invite list!")
        if not client.is_mod and not (client in client.area.owners) and client.char_id == -1:
            raise ClientError("You may not do that while spectating!")
        client.area.change_doc(arg)
        client.area.broadcast_ooc(f'{client.showname} changed the doc link to: {client.area.doc}')
        database.log_area('doc.change', client, client.area, message=arg)


def ooc_cmd_cleardoc(client, arg):
    """
    Elimina il link per il documento del caso attuale.
    Uso: /cleardoc
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.cannot_ic_interact(client):
        raise ClientError("You are not on the area's invite list!")
    if not client.is_mod and not (client in client.area.owners) and client.char_id == -1:
        raise ClientError("You may not do that while spectating!")
    client.area.change_doc()
    client.area.broadcast_ooc('{} cleared the doc link.'.format(
        client.showname))
    database.log_area('doc.clear', client, client.area)


@mod_only(area_owners=True)
def ooc_cmd_evidence_mod(client, arg):
    """
    Cambia il privilegio delle prove.
    Uso: /evidence_mod <FFA|Mods|CM|HiddenCM>
    """
    if not arg or arg == client.area.evidence_mod:
        client.send_ooc(
            f'current evidence mod: {client.area.evidence_mod}')
    elif arg in ['FFA', 'Mods', 'CM', 'HiddenCM']:
        if not client.is_mod:
            if client.area.evidence_mod == 'Mods':
                raise ClientError('You must be authorized to change this area\'s evidence mod from Mod-only.')
            if arg == 'Mods':
                raise ClientError('You must be authorized to set the area\'s evidence to Mod-only.')
        client.area.evidence_mod = arg
        client.area.broadcast_evidence_list()
        client.send_ooc(
            f'current evidence mod: {client.area.evidence_mod}')
        database.log_area('evidence_mod', client, client.area, message=arg)
    else:
        raise ArgumentError(
            'Wrong Argument. Use /evidence_mod <MOD>. Possible values: FFA, CM, Mods, HiddenCM'
        )


@mod_only(area_owners=True)
def ooc_cmd_evidence_swap(client, arg):
    """
    Scambia la posizione di due prove.
    l'ID iniziale è 0.
    Uso: /evidence_swap <id> <id>
    """
    args = list(arg.split(' '))
    if len(args) != 2:
        raise ClientError("you must specify 2 numbers")
    try:
        client.area.evi_list.evidence_swap(client, int(args[0])-1, int(args[1])-1)
        client.area.broadcast_evidence_list()
    except:
        raise ClientError("you must specify 2 numbers")


def ooc_cmd_cm(client, arg):
    """
    Aggiunge un CM nell'area attuale.
    Lascia l'id vuoto per rendere te stesso CM se non ce ne sono altri.
    Uso: /cm <id>
    """
    if not client.area.can_cm:
        raise ClientError('You can\'t become a CM in this area')
    if len(client.area.owners) == 0 or client.is_mod:
        if len(arg) > 0:
            raise ArgumentError(
                'You cannot \'nominate\' people to be CMs when you are not one.'
            )
        client.area.add_owner(client)
        database.log_area('cm.add', client, client.area, target=client, message='self-added')
    elif client in client.area.owners:
        if len(arg) > 0:
            arg = arg.split(' ')
        for id in arg:
            try:
                id = int(id)
                c = client.server.client_manager.get_targets(
                    client, TargetType.ID, id, False)[0]
                if not c in client.area.clients:
                    raise ArgumentError(
                        'You can only \'nominate\' people to be CMs when they are in the area.'
                    )
                elif c in client.area.owners:
                    client.send_ooc(
                        f'{c.showname} [{c.id}] is already a CM here.')
                else:
                    client.area.add_owner(c)
                    database.log_area('cm.add', client, client.area, target=c)
            except (ValueError, IndexError):
                client.send_ooc(
                    f'{id} does not look like a valid ID.')
            except (ClientError, ArgumentError):
                raise
    else:
        raise ClientError('You must be authorized to do that.')


@mod_only(area_owners=True)
def ooc_cmd_uncm(client, arg):
    """
    Rimuove un CM dall'area attuale	.
    Uso: /uncm <id>
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
            if c in client.area.owners:
                client.area.remove_owner(c)
                database.log_area('cm.remove', client, client.area, target=c)
            else:
                client.send_ooc(
                    'You cannot remove someone from CMing when they aren\'t a CM.'
                )
        except (ValueError, IndexError):
            client.send_ooc(
                f'{_id} does not look like a valid ID.')
        except (ClientError, ArgumentError):
            raise


# LEGACY
def ooc_cmd_setcase(client, arg):
    """
    Seleziona la posizione di cui sei interessato prendere durante un caso.
    Questo comando non è disponibile ma è possibile usarlo cliccando sul pulsante "casing" all'interno del client.
    """
    args = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', arg)
    if len(args) == 0:
        raise ArgumentError('Please do not call this command manually!')
    else:
        client.casing_cases = args[0]
        client.casing_cm = args[1] == "1"
        client.casing_def = args[2] == "1"
        client.casing_pro = args[3] == "1"
        client.casing_jud = args[4] == "1"
        client.casing_jur = args[5] == "1"
        client.casing_steno = args[6] == "1"


# LEGACY
def ooc_cmd_anncase(client, arg):
    """
    Annuncia che un caso si sta svolgendo nell'area attuale, necessita un certo numero di persone per essere riempita.
    Uso: /anncase <message> <def> <pro> <jud> <jur> <steno>
    """
    # XXX: Merge with aoprotocol.net_cmd_casea
    if client in client.area.owners:
        if not client.can_call_case():
            raise ClientError(
                'Please wait 60 seconds between case announcements!')
        args = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', arg)
        if len(args) == 0:
            raise ArgumentError('Please do not call this command manually!')
        elif len(args) == 1:
            raise ArgumentError(
                'You should probably announce the case to at least one person.'
            )
        else:
            if not args[1] == "1" and not args[2] == "1" and not args[
                    3] == "1" and not args[4] == "1" and not args[5] == "1":
                raise ArgumentError(
                    'You should probably announce the case to at least one person.'
                )
            msg = '=== Case Announcement ===\r\n{} [{}] is hosting {}, looking for '.format(
                client.showname, client.id, args[0])

            lookingfor = [p for p, q in
                zip(['defense', 'prosecutor', 'judge', 'juror', 'stenographer'], args[1:])
                if q == '1']

            msg += ', '.join(lookingfor) + '.\r\n=================='

            client.server.send_all_cmd_pred('CASEA', msg, args[1], args[2],
                                            args[3], args[4], args[5], '1')

            client.set_case_call_delay()

            log_data = {k: v for k, v in
                zip(('message', 'def', 'pro', 'jud', 'jur', 'steno'), args)}
            database.log_area('case', client, client.area, message=log_data)
    else:
        raise ClientError(
            'You cannot announce a case in an area where you are not a CM!')


@mod_only()
def ooc_cmd_blockwtce(client, arg):
    """
    Previene l'utilizzo di un utente dei pulsanti "Testimony" e "Cross Examination" in posizione di giudice.
    Uso: /blockwtce <id>
    """
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /blockwtce <id>.')
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must enter a number. Use /blockwtce <id>.')
    if not targets:
        raise ArgumentError('Target not found. Use /blockwtce <id>.')
    for target in targets:
        target.can_wtce = False
        target.send_ooc(
            'A moderator blocked you from using judge signs.')
        database.log_area('blockwtce', client, client.area, target=target)
    client.send_ooc('blockwtce\'d {}.'.format(
        targets[0].char_name))


@mod_only()
def ooc_cmd_unblockwtce(client, arg):
    """
    Rimuove il blocco sull'utilizzo dei comandi "Testimony" e "Cross Examination" in posizione di giudice.
    Uso: /unblockwtce <id>
    """
    if len(arg) == 0:
        raise ArgumentError(
            'You must specify a target. Use /unblockwtce <id>.')
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must enter a number. Use /unblockwtce <id>.')
    if not targets:
        raise ArgumentError('Target not found. Use /unblockwtce <id>.')
    for target in targets:
        target.can_wtce = True
        target.send_ooc(
            'A moderator unblocked you from using judge signs.')
        database.log_area('unblockwtce', client, client.area, target=target)
    client.send_ooc('unblockwtce\'d {}.'.format(
        targets[0].char_name))


@mod_only()
def ooc_cmd_judgelog(client, arg):
    """
    Mostra gli ultimi 10 utilizzi dei comandi del giudice nell'area attuale.
    Uso: /judgelog
    """
    if len(arg) != 0:
        raise ArgumentError('This command does not take any arguments.')
    jlog = client.area.judgelog
    if len(jlog) > 0:
        jlog_msg = '== Judge Log =='
        for x in jlog:
            jlog_msg += f'\r\n{x}'
        client.send_ooc(jlog_msg)
    else:
        raise ServerError(
            'There have been no judge actions in this area since start of session.'
        )


def ooc_cmd_afk(client, arg):
    client.server.client_manager.toggle_afk(client)


@mod_only(area_owners=True)
def ooc_cmd_remote_listen(client, arg):
    """
    Cambia la lettura dei log a NONE, IC, OOC o ALL.
    Manderà quel tipo di messaggi dalle aree in cui sei CM o GM.
    Lascialo vuoto per vedere la tua corrente impostazione.
    Usage: /remote_listen [option]
    """
    options = {
        'NONE': 0,
        'IC': 1,
        'OOC': 2,
        'ALL': 3,
    }
    if arg != '':
        try:
            client.remote_listen = options[arg.upper()]
        except KeyError:
            raise ArgumentError('Invalid option! Your options are NONE, IC, OOC or ALL.')
    reversed_options = dict(map(reversed, options.items()))
    opt = reversed_options[client.remote_listen]
    client.send_ooc(f'Your current remote listen option is: {opt}')


def ooc_cmd_testimony(client, arg):
    """
    Mostra la testimonianza attualmente registrata.
    Opzinalmente, l'id può essere usato per muoversi alla testimonianza corrisponente.
    Uso: /testimony [id]
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc('There is no testimony recorded!')
        return
    args = arg.split()
    if len(args) > 0:
        try:
            if client.area.recording == True:
                client.send_ooc('It is not cross-examination yet!')
                return
            idx = int(args[0]) - 1
            client.area.testimony_send(idx)
            client.area.broadcast_ooc(f'{client.showname} has moved to Statement {idx+1}.')
        except ValueError:
            raise ArgumentError('Index must be a number!')
        except ClientError:
            raise
        return

    msg = f'Use > IC to progress, < to backtrack, >3 or <3 to go to specific statements.'
    msg += f'\n-- {client.area.testimony_title} --'
    for i, statement in enumerate(client.area.testimony):
        # [15] SHOWNAME
        name = statement[15]
        if name == '' and statement[8] != -1:
            # [8] CID
            name = client.server.char_list[statement[8]]
        txt = statement[4].replace('{', '').replace('}', '')
        here = '  '
        if i == client.area.testimony_index:
            here = ' >'
        msg += f'\n{here}{i+1}) {name}: {txt}'
    client.send_ooc(msg)


@mod_only(area_owners=True)
def ooc_cmd_testimony_start(client, arg):
    """
    Fa partire una serie di testimonianze con un titolo dato.
    Uso: /testimony_start <title>
    """
    if arg == '':
        raise ArgumentError('You must provite a title! /testimony_start <title>.')
    if len(arg) < 3:
        raise ArgumentError('Title must contain at least 3 characters!')
    client.area.testimony.clear()
    client.area.testimony_index = -1
    client.area.testimony_title = arg
    client.area.recording = True
    client.area.broadcast_ooc(f'-- {client.area.testimony_title} --\nTestimony recording started! All new messages will be recorded as testimony lines. Say "End" to stop recording.')

@mod_only(area_owners=True)
def ooc_cmd_testimony_clear(client, arg):
    """
    Cancella la/e testimonianza/e attualmente registrata/e.
    Uso: /testimony_clear
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc('There is no testimony recorded!')
        return
    if len(arg) != 0:
        raise ArgumentError('This command does not take any arguments.')
    client.area.testimony.clear()
    client.area.testimony_title = ''
    client.area.broadcast_ooc(f'{client.showname} cleared the current testimony.')


@mod_only(area_owners=True)
def ooc_cmd_testimony_remove(client, arg):
    """
    Cancella completamente la registrazione di una testimonianza.
    Uso: /testimony_remove <id>
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc('There is no testimony recorded!')
        return
    args = arg.split()
    if len(args) <= 0:
        raise ArgumentError('Usage: /testimony_remove <idx>.')
    try:
        idx = int(args[0]) - 1
        client.area.testimony.pop(idx)
        if client.area.testimony_index == idx:
            client.area.testimony_index = -1
        client.area.broadcast_ooc(f'{client.showname} has removed Statement {idx+1}.')
    except ValueError:
        raise ArgumentError('Index must be a number!')
    except IndexError:
        raise ArgumentError('Index out of bounds!')
    except ClientError:
        raise


@mod_only(area_owners=True)
def ooc_cmd_testimony_amend(client, arg):
    """
    Cambia la testimonianza durante una registrazione scrivendo l'ID del mandante.
    Uso: /testimony_amend <id> <msg>
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc('There is no testimony recorded!')
        return
    args = arg.split()
    if len(args) < 2:
        raise ArgumentError('Usage: /testimony_remove <id> <msg>.')
    try:
        idx = int(args[0]) - 1
        lst = list(client.area.testimony[idx])
        lst[4] = "}}}" + args[1:]
        client.area.testimony[idx] = tuple(lst)
        client.area.broadcast_ooc(f'{client.showname} has amended Statement {idx+1}.')
    except ValueError:
        raise ArgumentError('Index must be a number!')
    except IndexError:
        raise ArgumentError('Index out of bounds!')
    except ClientError:
        raise


@mod_only(area_owners=True)
def ooc_cmd_testimony_swap(client, arg):
    """
    Scambia due testimonianze tramite ID.
    Uso: /testimony_swap <id> <id>
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc('There is no testimony recorded!')
        return
    args = arg.split()
    if len(args) < 2:
        raise ArgumentError('Usage: /testimony_remove <id> <id>.')
    try:
        idx1 = int(args[0]) - 1
        idx2 = int(args[1]) - 1
        client.area.testimony[idx2], client.area.testimony[idx1] = client.area.testimony[idx1], client.area.testimony[idx2]
        client.area.broadcast_ooc(f'{client.showname} has swapped Statements {idx1+1} and {idx2+1}.')
    except ValueError:
        raise ArgumentError('Index must be a number!')
    except IndexError:
        raise ArgumentError('Index out of bounds!')
    except ClientError:
        raise

@mod_only(area_owners=True)
def ooc_cmd_cs(client, arg):
    """
    Inizia un dibattito uno contro uno con il giocatore selezionato (Cross Swords)!
    Termina in 5 minuti. Se è presente già un altro dibattito, si trasformerà in uno Scrum Debate (dibattito tra team)
    con te che entrerai dalla parte opposta all'id immesso.
    Uso: /cs <id>
    """
    if arg == '':
        if client.area.minigame_schedule and not client.area.minigame_schedule.cancelled():
            msg = f'Current minigame is {client.area.minigame}!'
            red = []
            for cid in client.area.red_team:
                name = client.server.char_list[cid]
                for c in client.area.clients:
                    if c.char_id == cid:
                        name = f'[{c.id}] {c.showname}'
                red.append(f'🔴{name} (Red)')
            msg += '\n'.join(red)
            msg += '\n⚔VERSUS⚔\n'
            blue = []
            for cid in client.area.blue_team:
                name = client.server.char_list[cid]
                for c in client.area.clients:
                    if c.char_id == cid:
                        name = f'[{c.id}] {c.showname}'
                blue.append(f'🔵{name} (Blue)')
            msg += '\n'.join(blue)
            msg += f'\n⏲{int(client.area.minigame_time_left)} seconds left.'
            client.send_ooc(msg)
        else:
            client.send_ooc('There is no minigame running right now.')
        return
    args = arg.split()
    try:
        target = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), True)[0]
    except:
        raise ArgumentError('Target not found.')
    else:
        try:
            pta = False
            if len(args) > 1:
                pta = args[1] == '1'
            prev_mini = client.area.minigame
            client.area.start_debate(client, target, pta=pta)
            if prev_mini != client.area.minigame:
                us = f'[{client.id}] ~{client.showname}~'
                them = f'[{target.id}] √{target.showname}√'
                if client.area.minigame == 'Scrum Debate':
                    for cid in client.area.blue_team:
                        if client.char_id == cid:
                            us = f'[{client.id}] √{client.showname}√'
                            them = f'[{target.id}] ~{target.showname}~'
                            break
                msg = f'~~}}}}`{client.area.minigame}!`\\n{us} objects to {them}!'
                client.area.send_ic(None, '1', 0, "", "../misc/blank", msg, "", "", 0, -1, 0, 2, [0], 0, 0, 0, "System", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        except AreaError as ex:
            raise ex

@mod_only(area_owners=True)
def ooc_cmd_pta(client, arg):
    """
    Inizia un dibattito uno contro uno con il giocatore selezionato (Panic Talk action)!
    Al contrario di /cs, una Panic Talk Action (PTA) non può evolversi in uno Scrum Debate.
    Termina dopo 5 minuti.
    Uso: /pta <id>
    """
    args = arg.split()
    ooc_cmd_cs(client, f'{args[0]} 1')

def ooc_cmd_concede(client, arg):
    """
    Termina un minigioco e fa perdere la squadra di chi ha effettuato il comando.
    Uso: /concede
    """
    if client.area.minigame != '':
        try:
            if arg.lower() == 'not-pta' and client.area.minigame == 'Panic Talk Action':
                client.send_ooc('Current minigame is Panic Talk Action - not conceding this one.')
                return
            # CM's end the minigame automatically using /concede
            if client in client.area.owners:
                client.area.end_minigame('Forcibly ended.')
                client.area.broadcast_ooc('The minigame has been forcibly ended.')
                return
            client.area.start_debate(client, client) # starting a debate against yourself is a concede
        except AreaError as ex:
            raise ex
    else:
        client.send_ooc('There is no minigame running right now.')


def ooc_cmd_case_list(client, arg):
    import inspect
    msg = inspect.cleandoc('''https://docs.google.com/document/d/1bu4onPCE-U-NARLkuEyIXeFQOinqDFyM2495YO9-9LE/edit?usp=sharing''')
    client.send_ooc(msg)