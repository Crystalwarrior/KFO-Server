import random
import shlex
from threading import Timer

import asyncio
import numpy as np
import arrow
import datetime
import pytimeparse

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError

from . import mod_only
from .. import commands

__all__ = [
    'ooc_cmd_cc',
    'ooc_cmd_cstat',
    'ooc_cmd_cpg',
    'ooc_cmd_ba',
    'ooc_cmd_am',
    'ooc_cmd_mov',
    'ooc_cmd_atk', 
    'ooc_cmd_def',
    'ooc_cmd_surrender',
    'ooc_cmd_remove_mov',
    'ooc_cmd_remove_pg',
    'ooc_cmd_mov_list',
    'ooc_cmd_showdown',
    'ooc_cmd_showdownatk',
    'ooc_cmd_refresh_showdown',
    'ooc_cmd_rstat',
    'ooc_cmd_showdownsurrender', 
    'ooc_cmd_remove_showdown',
    'ooc_cmd_showdown_list',
]

def ooc_cmd_cc(client, arg):
   args = shlex.split(arg)
   if len(args) == 7:
     f = open('storage/battlesystem/battlesystem.yaml', 'r')
     lines = f.readlines()
     i = 0
     personaggi = []
     for line in lines:
      if "Character:" in line:
       personaggi.append(line)
     for line in personaggi:
      if args[0] in line:
       i = -1
     if i == 0:
        max = float(args[2])+float(args[3])+float(args[4])+float(args[5])+float(args[6])
        if max > 200:
         client.send_ooc('Personaggio non creato poichè la somma delle statistiche di base supera i 200 punti, prova a diminuirne una')
         return
        righe = len(lines)
        lines.append(f'Character: {args[0]}')
        lines.append(f'  Sprite: {args[1]}')
        lines.append(f'  Client: {client}')
        lines.append(f'  HP: {args[2]}')
        lines.append(f'  ATK: {args[3]}')
        lines.append(f'  DEF: {args[4]}')
        lines.append(f'  SPA: {args[5]}')
        lines.append(f'  SPD: {args[6]}\n =================================================================')
        f = open('storage/battlesystem/battlesystem.yaml', 'w')
        for line in lines:
         if lines.index(line) < righe:
           f.write(f'{line}')
         elif lines.index(line) == righe:
           f.write(f'\n\n{line}')
         else: 
          if lines.index(line) == len(lines):
           f.write(f'\n{line}\n')
          else: 
           f.write(f'\n{line}')
        client.send_ooc(f'{args[0]} creato!')
     else:
       client.send_ooc('Nome Personaggio già in uso')

   else:
     client.send_ooc('Non hai inserito tutte le informazioni')

def ooc_cmd_cstat(client, arg):
  b = client
  if not arg == "":
   for hub in client.server.hub_manager.hubs:
       for area in hub.areas:
         for c in area.clients:
           if c.pg == arg:
              client = c
  if not client.pg == "":
   msg = f"\n {client.pg} specifiche:\n\nHP: {client.hp}\nATK: {client.atk}\nDEF: {client.defe}\nSPA: {client.spa}\nSPD: {client.spd}"
   b.send_ooc(msg)
       
def ooc_cmd_cpg(client, arg, Yesbg = True):
   if not arg == "":
     f = open('storage/battlesystem/battlesystem.yaml', 'r')
     lines = f.readlines()
     personaggi = []
     j = -1
     for line in lines:
      if f"Character: {arg}\n" == line:
       j = lines.index(line)
     if not j == -1:
      lines[j+2] = f'  Client: {client.hdid}\n'
      charsel = lines[j+1].split(": ")[1].split("\n")[0]
      line = lines[j].split(": ")[1].split("\n")[0]
      client.pg = line
      client.hp = float(lines[j+3].split(": ")[1].split("\n")[0])
      client.maxhp = client.hp
      client.atk = float(lines[j+4].split(": ")[1].split("\n")[0])
      client.defe = float(lines[j+5].split(": ")[1].split("\n")[0])
      client.spa = float(lines[j+6].split(": ")[1].split("\n")[0])
      client.spd = float(lines[j+7].split(": ")[1].split("\n")[0])
      if Yesbg:
       client.send_ooc(f'Sei stato aggiunto come {line}!')
       msg = f'{client.id} {charsel}'
       client.area.add_owner(client)
       commands.character.ooc_cmd_charselect(client, msg)
       bg = client.area.background
       client.area.remove_owner(client)
       commands.areas.ooc_cmd_bg(client, bg)
       f = open('storage/battlesystem/battlesystem.yaml', 'w')
       client.area.send_ic(None, '1', 0, "", f"../characters/{charsel}/default", "", "", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
       commands.character.ooc_cmd_pos(client, 'wit')
       for line in lines:
        f.write(line)
     else:
      client.send_ooc('Personaggio non trovato')




def ooc_cmd_ba(client, arg):
 Attaccante = client.area.Attaccante
 Difensore = client.area.Difensore
 if client.area.ba[0] == -1:
  if not arg == "":
     f = open('storage/battlesystem/battlesystem.yaml', 'r')
     lines = f.readlines()
     V = False
     for line in lines:
       if client.hdid in line:
        j = lines.index(line) 
        V = True
     Atk = lines[j-1].split(": ")[1].split("\n")[0]
     if V:
      V = False
      target = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(arg), False)[0] 
      for line in lines:
         if target.pg in line:
            V = True
            j = lines.index(line)
      Def = lines[j+1].split(": ")[1].split("\n")[0]
      if V:
       import random
       turno = random.randint(0,1)
       if turno == 0:
        client.area.send_ic(None, '1', 0, "", f"../characters/{client.char_name}/default", f"~~ ~ }} {client.pg}", f"{client.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, "", f"../misc/battle", "~~ ~ }}ATTACCA", f"{client.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, "", f"../characters/{target.char_name}/default", f"~~ ~ }} {target.pg}", f"{target.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.ba[0] = 0
        Attaccante.append(client)
        Difensore.append(target)
        Attaccante[0].paralisi = ""
        Attaccante[0].veleno = ""
        Difensore[0].paralisi = ""
        Difensore[0].veleno = ""
        Attaccante[0].mossa = ""
        Difensore[0].mossa = ""
        client.area.requiem = -1
       else:
        t = Atk
        Atk = Def
        Def = t
        client.area.send_ic(None, '1', 0, "", f"../characters/{target.char_name}/default", f"~~ ~ }} {target.pg}", f"{target.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, "", f"../misc/battle", "~~ ~ }}ATTACCA", f"{target.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, "", f"../characters/{client.char_name}/default", f"~~ ~ }} {client.pg}", f"{client.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.ba[0] = 0
        Attaccante.append(target)
        Difensore.append(client)
        Attaccante[0].paralisi = ""
        Attaccante[0].veleno = ""
        Difensore[0].paralisi = ""
        Difensore[0].veleno = ""
        Attaccante[0].mossa = ""
        Difensore[0].mossa = ""
        client.area.requiem = -1
      else:
        client.send_ooc("Non hai inserito bene il nome l'id dello sfidante") 
     else:
       client.send_ooc('Non hai scelto un personaggio')
  else:
     client.send_ooc("Non hai inserito bene il nome l'id dello sfidante")
 else:
     client.send_ooc("C'è già una battaglia in corso")

def ooc_cmd_am(client,arg):
   if not arg == "":
     f = open('storage/battlesystem/battlesystem.yaml', 'r')
     lines = f.readlines()
     V = False
     for line in lines:
        if f'Character: {client.pg}' in line:
          pgi = lines.index(line)
          V = True
     if V == True:
        pgi = pgi+7
        args = shlex.split(arg)
        if args[1] == 'Atk' or args[1] == 'Spa':
          tot = int(args[2])+50*(len(args)-3)
          if tot > 120:
            client.send_ooc('Questa mossa è troppo forte prova a ridurre la potenza o gli effetti!')
            return
        if args[1] == 'Def' or args[1] == 'Spd':
          tot = 50*(len(args)-3)
          if tot > 50:
           client.send_ooc('Questa mossa è troppo forte prova a ridurre la potenza o gli effetti!')
           return
        msg = f'  MovesName: {args[0]} {client.pg}\n'    
        if args[1] == 'Atk' or args[1] == 'Def' or args[1] == 'Spa' or args[1] == 'Spd':
          msg += f'  MovesType: {args[1]}\n'
        else:
          client.send_ooc('Gli unici tipi di attacchi sono Atk Spa Def Spd')
          return
        if args[1] == 'Def' or args[1] == 'Spd':
         msg += f'  Power: 0\n'
         args[2] = 0
        else:
         if args[2].isnumeric():
          msg += f'  Power: {args[2]}\n'
         else:
          client.send_ooc('Devi mettere un valore numerico alla mossa!')
          return
        if 'Paralysis' in arg:
         msg += f'  Paralysis: Yes\n'
        else:
         msg += f'  Paralysis: No\n'
        if 'Poison' in arg:
         msg += f'  Poison: Yes\n'
        else:
         msg += f'  Poison: No\n'
        if 'DefDown' in arg:
         msg += f'  DefDown: Yes\n'
        else:
         msg += f'  DefDown: No\n'
        if 'AtkDown' in arg:
         msg += f'  AtkDown: Yes\n'
        else:
         msg += f'  AtkDown: No\n'
        if 'SpaDown' in arg:
         msg += f'  SpaDown: Yes\n'
        else:
         msg += f'  SpaDown: No\n'
        if 'SpdDown' in arg:
         msg += f'  SpdDown: Yes\n'
        else:
         msg += f'  SpdDown: No\n'
        if 'AtkRaise' in arg:
         msg += f'  AtkRaise: Yes\n'
        else:
         msg += f'  AtkRaise: No\n'
        if 'DefRaise' in arg:
         msg += f'  DefRaise: Yes\n'
        else:
         msg += f'  DefRaise: No\n'
        if 'SpaRaise' in arg:
         msg += f'  SpaRaise: Yes\n'
        else:
         msg += f'  SpaRaise: No\n'
        if 'SpdRaise' in arg:
         msg += f'  SpdRaise: Yes\n'
        else:
         msg += f'  SpdRaise: No\n'
        if 'Heal' in arg:
         msg += f'  Heal: Yes\n'
        else:
         msg += f'  Heal: No\n'
        if 'StealStat' in arg:
         msg += f'  StealStat: Yes\n'
        else:
         msg += f'  StealStat: No\n'
        if 'Requiem' in arg:
         msg += f'  Requiem: Yes\n'
        else:
         msg += f'  Requiem: No\n'
        if 'HAlly' in arg:
         msg += f'  HAlly: Yes\n'
        else:
         msg += f'  HAlly: No\n'
        if 'AtkAll' in arg:
         msg += f'  AtkAll: Yes\n'
        else:
         msg += f'  AtkAll: No\n'
        lines[pgi] = f'{lines[pgi]}{msg}'
        f = open('storage/battlesystem/battlesystem.yaml', 'w')
        for line in lines:
          f.write(line)
        f = open('storage/battlesystem/battlesystem.yaml', 'r')
        lines.clear()
        lines = f.readlines()
        msg = f'\n{args[0]} Specifiche:\n Tipo: {args[1]}\n Potenza: {args[2]}\n Effetti:\n'
        for i in range(4,19):
         if 'Yes' in lines[pgi+i]:
           lines[pgi+i] = lines[pgi+i].split(':')[0]
           msg += lines[pgi+i]
        client.send_ooc(msg)
     else:
       client.send_ooc('Non hai ancora scelto un personaggio')
   else:
    client.send_ooc('Non hai inserito bene le info')
                          
def ooc_cmd_mov(client, arg):
 if not arg == "":
  f = open('storage/battlesystem/battlesystem.yaml', 'r')
  lines = f.readlines()
  id = -1
  for line in lines:
   if arg in line:
     id = lines.index(line)
  if not id == -1:
   tipo = lines[id+1].split(": ")[1].split("\n")[0]
   potenza = lines[id+2].split(": ")[1].split("\n")[0]
   msg = f'\n {arg} Specifiche:\n Tipo: {tipo}\n Potenza: {potenza}\n Effetti:\n'
   for i in range(3,19):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0]
           msg += lines[id+i]
   client.send_ooc(msg)
  else:
   client.send_ooc('Mossa non trovata')
 else:
  client.send_ooc('Non hai scelto nessuna mossa!')

def ooc_cmd_atk(client, arg):
 Attaccante = client.area.Attaccante
 Difensore = client.area.Difensore
 if not arg == "":
  if client in Attaccante:
   if client.mossa == "":
     if client.area.ba[0] == 0:
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if client.pg in lines[id]:
       if not 'Def' in lines[id+1] and not 'Spd' in lines[id+1]:
        client.mossa = arg
        client.send_ooc('Mossa Selezionata!')
        client.area.ba[0] = 1
       else:
        client.send_ooc('Non puoi usare una mossa di tipo difensivo per attaccare')
      else:
       client.send_ooc('Non puoi usare una mossa che non è tua!')
     elif client.area.ba[0] == 1:
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if client.pg in lines[id]:
       if not 'Def' in lines[id+1] and not 'Spd' in lines[id+1]:
        client.mossa = arg
        client.send_ooc('Mossa Selezionata!')
        inizio_battaglia(Attaccante, Difensore)
       else:
        client.send_ooc('Non puoi usare una mossa di tipo difensivo per attaccare')
      else:
       client.send_ooc('Non puoi usare una mossa che non è tua!')
     else:
      client.send_ooc('Non è iniziata alcuna battaglia')
   else:
    client.send_ooc("Hai già selezionato l'attacco!")
  else:
    client.send_ooc('Non stai attaccando')
 else:
   client.send_ooc('Non hai selezionato nessun attacco!')

def ooc_cmd_def(client, arg):
 Attaccante = client.area.Attaccante
 Difensore = client.area.Difensore
 if not arg == "":
  if client in Difensore:
   if client.mossa == "":
     if client.area.ba[0] == 0:
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if client.pg in lines[id]:
       if not 'Atk' in lines[id+1] and not 'Spa' in lines[id+1]:
        client.mossa = arg
        client.send_ooc('Mossa Selezionata!')
        client.area.ba[0] = 1
       else:
        client.send_ooc("Non puoi usare una mossa d'attacco per difendere")
      else:
       client.send_ooc('Non puoi usare una mossa che non è tua!')
     elif client.area.ba[0] == 1:
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      id = -1
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if not id == -1 and client.pg in lines[id]:
       if not 'Atk' in lines[id+1] and not 'Spa' in lines[id+1]:
        client.mossa = arg
        client.send_ooc('Mossa Selezionata!')
        inizio_battaglia(Attaccante, Difensore)
       else:
        client.send_ooc("Non puoi usare una mossa d'attacco per difendere")
      else:
       client.send_ooc('Non puoi usare una mossa che non è tua!')
     else:
      client.send_ooc('Non è iniziata alcuna battaglia')
   else:
    client.send_ooc("Hai già selezionato la mossa!")
  else:
    client.send_ooc('Non stai difendendo')
 else:
   client.send_ooc('Non hai selezionato alcuna mossa!')

paralisi = [1, 2, 3]
critic = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

def inizio_battaglia(Attaccante, Difensore):
  f = open('storage/battlesystem/battlesystem.yaml', 'r')
  lines = f.readlines()
  for line in lines:
   if Attaccante[0].mossa in line:
     id = lines.index(line)
  ATTtipo = lines[id+1].split(": ")[1].split("\n")[0]
  ATTpotenza = float(lines[id+2].split(": ")[1].split("\n")[0])
  AttEffect = []
  AttEffect.clear()
  for i in range(3,17):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0].split('  ')[1]
           AttEffect.append(lines[id+i])
  for line in lines:
   if Difensore[0].mossa in line:
     id = lines.index(line)
  DEFtipo = lines[id+1].split(": ")[1].split("\n")[0]
  DefEffect = []
  DefEffect.clear()
  for i in range(3,17):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0].split('  ')[1]
           DefEffect.append(lines[id+i])
  paralyse = list(np.random.permutation(np.arange(0,len(paralisi))))
  id_char = Difensore[0].server.char_list.index(Difensore[0].char_name)
  crit = list(np.random.permutation(np.arange(0,len(critic))))
  if Attaccante[0].paralisi == "paralisi" and paralyse[0] == 2:
   Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} \f\s {Attaccante[0].pg}  è ~paralizzato~ e non riesce ad attaccare", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  elif Difensore[0].paralisi == "paralisi" and paralyse[0] == 2:
   Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} \f\s {Difensore[0].pg}  è ~paralizzato~ e non riesce a difendersi", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   Attaccante[0].area.ba[0] = 0
   if ATTtipo == "Atk":
    if crit[0] == 1:
     danno = ATTpotenza*Attaccante[0].atk*4//(Difensore[0].defe*3)
     Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} prepara un ~attacco critico~!", f"{Attaccante[0].pos}", f"{Attaccante[0].pos}", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    else:
     danno = ATTpotenza*Attaccante[0].atk*2//(Difensore[0].defe*3)
   else:
    if crit[0] == 1:
     Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} prepara un ~attacco critico~!", f"{Attaccante[0].pos}", f"{Attaccante[0].pos}", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     danno = ATTpotenza*Attaccante[0].spa*4//(Difensore[0].spd*3)
    else:
     danno = ATTpotenza*Attaccante[0].spa*2//(Difensore[0].spd*3)
   Difensore[0].hp = Difensore[0].hp - danno
   Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} attacca con ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", f"{Attaccante[0].pos}", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
   if ATTtipo == "Spa":
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Difensore[0].pg} è paralizzato e perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", f"{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   else:
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Difensore[0].pg} è paralizzato e perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", f"{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  else:
   d = 1
   if (ATTtipo == "Atk" and DEFtipo == "Def") or (ATTtipo == "Spa" and DEFtipo == "Spd"):
    d = 0.5
   if ATTtipo == "Atk":
    if crit[0] == 1:
     Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} prepara un ~attacco critico~!", f"{Attaccante[0].pos}", f"{Attaccante[0].pos}", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     danno = ATTpotenza*Attaccante[0].atk*d*2//(Difensore[0].defe*3)
    else:
     danno = ATTpotenza*Attaccante[0].atk*d//(Difensore[0].defe*3)
   if ATTtipo == "Spa":
    if crit[0] == 1:
     Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} prepara un ~attacco critico~!", f"{Attaccante[0].pos}", f"{Attaccante[0].pos}", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     danno = ATTpotenza*Attaccante[0].spa*d*2//(Difensore[0].spd*3)
    else:
     danno = ATTpotenza*Attaccante[0].spa*d//(Difensore[0].spd*3)
   if not danno == 0:
    Difensore[0].hp = Difensore[0].hp - danno
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} attacca con ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", f"{Attaccante[0].pos}", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    if ATTtipo == "Atk": 
     Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Difensore[0].pg} si difende con ~{Difensore[0].mossa}~, ma perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", f"{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    else:
     Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Difensore[0].pg} si difende con ~{Difensore[0].mossa}~, ma perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", f"{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    Attaccante[0].area.ba[0] = 0
   else:
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} usa ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", f"{Attaccante[0].pos}", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    Attaccante[0].area.ba[0] = 0
   if 'Paralysis' in AttEffect:
    if not Difensore[0].paralisi == "paralisi":
       Difensore[0].paralisi = "paralisi"
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} \f\s {Difensore[0].pg} è affetto dalla paralisi per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Poison' in AttEffect:
    if not Difensore[0].veleno == "avvelenato":
       Difensore[0].veleno = "avvelenato"
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} \f\s  {Difensore[0].pg} è affetto dall'avvelenamento per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefDown' in AttEffect:
       Difensore[0].defe = Difensore[0].defe*0.75
       if Difensore[0].defe < 10:
         Difensore[0].defe = 10
       Attaccante[0].area.send_ic(None, '1', '-', "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} La difesa di {Difensore[0].pg} diminuisce per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkDown' in AttEffect:
       Difensore[0].atk = Difensore[0].atk*0.75
       if Difensore[0].atk < 10:
         Difensore[0].atk = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} L'attacco di {Difensore[0].pg} diminuisce per via di  ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaDown' in AttEffect:
       Difensore[0].spa = Difensore[0].spa*0.75
       if Difensore[0].spa < 10:
         Difensore[0].spa = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} L'attacco speciale di {Difensore[0].pg} diminuisce per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdDown' in AttEffect:
       Difensore[0].spd = Difensore[0].spd*0.75
       if Difensore[0].spd < 10:
         Difensore[0].spd = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} La difesa speciale di {Difensore[0].pg} diminuisce per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkRaise' in AttEffect:
       Attaccante[0].atk = Attaccante[0].atk*1.5
       if Attaccante[0].atk > 200:
          Attaccante[0].atk = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} L'attacco di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefRaise' in AttEffect:
       Attaccante[0].defe = Attaccante[0].defe*1.5
       if Attaccante[0].defe > 200:
          Attaccante[0].defe = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} La difesa di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaRaise' in AttEffect:
       Attaccante[0].spa = Attaccante[0].spa*1.5
       if Attaccante[0].spa > 200:
          Attaccante[0].spa = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} L'attacco speciale di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdRaise' in AttEffect:
       Attaccante[0].spd = Attaccante[0].spd*1.5
       if Attaccante[0].spd > 200:
          Attaccante[0].spd = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} La difesa speciale di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Heal' in AttEffect:
       Attaccante[0].hp = Attaccante[0].hp + Attaccante[0].maxhp//4
       if Attaccante[0].hp > Attaccante[0].maxhp:
          Attaccante[0].hp = Attaccante[0].maxhp
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} {Attaccante[0].pg} ha curato la propria vita per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'StealStat' in AttEffect:
       Attaccante[0].atk = Difensore[0].atk
       Attaccante[0].defe = Difensore[0].defe
       Attaccante[0].spa = Difensore[0].spa
       Attaccante[0].spd = Difensore[0].spd
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} {Attaccante[0].pg} ha rubato le statistiche dell'avversario per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Requiem' in AttEffect:
    if Attaccante[0].area.requiem == -1:
      Attaccante[0].area.requiem = 3
      Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} {Attaccante[0].pg} ha attivato il requiem per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Paralysis' in DefEffect:
    if not Attaccante[0].paralisi == "paralisi":
       Attaccante[0].paralisi = "paralisi"
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} \f\s {Attaccante[0].pg} è affetto dalla paralisi per via di ~{Difensore[0].mossa}~", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Poison' in DefEffect:
    if not Attaccante[0].veleno == "avvelenato":
       Attaccante[0].veleno = "avvelenato"
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} \f\s  {Attaccante[0].pg} è affetto dall'avvelenamento per via di ~{Difensore[0].mossa}~", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefDown' in DefEffect:
       Attaccante[0].defe = Attaccante[0].defe*0.75
       if Attaccante[0].defe < 10:
          Attaccante[0].defe = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} La difesa di {Attaccante[0].pg} diminuisce per via di ~{Difensore[0].mossa}~", f"{Attaccante[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkDown' in DefEffect:
       Attaccante[0].atk = Attaccante[0].atk*0.75
       if Attaccante[0].atk < 10:
          Attaccante[0].atk = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} L'attacco di {Attaccante[0].pg} diminuisce per via di ~{Difensore[0].mossa}~", f"{Attaccante[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaDown' in DefEffect:
       Attaccante[0].spa = Attaccante[0].spa*0.75
       if Attaccante[0].spa < 10:
          Attaccante[0].spa = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} L'attacco speciale di {Attaccante[0].pg} diminuisce per via di ~{Difensore[0].mossa}~", f"{Attaccante[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdDown' in DefEffect:
       Attaccante[0].spd = Attaccante[0].spd*0.75
       if Attaccante[0].spd < 10:
          Attaccante[0].spd = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} La difesa speciale di {Attaccante[0].pg} diminuisce per via di ~{Difensore[0].mossa}~", f"{Attaccante[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkRaise' in DefEffect:
       Difensore[0].atk = Difensore[0].atk*1.5
       if Difensore[0].atk > 200:
          Difensore[0].atk = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} L'attacco di {Difensore[0].pg} aumenta per via di ~{Difensore[0].mossa}~", f"{Difensore[0].pos}", "statsup", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefRaise' in DefEffect:
       Difensore[0].defe = Difensore[0].defe*1.5
       if Difensore[0].defe > 200:
          Difensore[0].defe = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} La difesa di {Difensore[0].pg} aumenta per via di ~{Difensore[0].mossa}~", f"{Difensore[0].pos}", "statsup", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaRaise' in DefEffect:
       Difensore[0].spa = Difensore[0].spa*1.5
       if Difensore[0].spa > 200:
          Difensore[0].spa = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} L'attacco speciale di {Difensore[0].pg} aumenta per via di ~{Difensore[0].mossa}~", f"{Difensore[0].pos}", "statsup", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdRaise' in DefEffect:
       Difensore[0].spd = Difensore[0].spd*1.5
       if Difensore[0].spd > 200:
          Difensore[0].spd = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} La difesa speciale di {Difensore[0].pg} aumenta per via di ~{Difensore[0].mossa}~", f"{Difensore[0].pos}", "statsup", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Heal' in DefEffect:
       Difensore[0].hp = Difensore[0].hp + Difensore[0].maxhp//4
       if Difensore[0].hp > Difensore[0].maxhp:
          Difensore[0].hp = Difensore[0].maxhp
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} {Difensore[0].pg} ha curato la propria vita per via di ~{Difensore[0].mossa}~", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'StealStat' in DefEffect:
       Difensore[0].atk = Difensore[0].atk
       Difensore[0].defe = Difensore[0].defe
       Difensore[0].spa = Difensore[0].spa
       Difensore[0].spd = Difensore[0].spd
       Difensore[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} {Difensore[0].pg} ha rubato le statistiche dell'avversario per via di ~{Difensore[0].mossa}~", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Requiem' in DefEffect:
     if Attaccante[0].area.requiem == -1:
      Attaccante[0].area.requiem = 3
      Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} {Difensore[0].pg} ha attivato il requiem per via di ~{Difensore[0].mossa}~", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if Difensore[0].veleno == "avvelenato":
    Difensore[0].hp = Difensore[0].hp - Difensore[0].maxhp//12
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} \f\s {Difensore[0].pg} è avvelenato e perde ~{Difensore[0].maxhp//12} hp~", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if Attaccante[0].veleno == "avvelenato":
    Attaccante[0].hp = Attaccante[0].hp - Attaccante[0].maxhp//12
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Defense", f"~~ }} \f\s {Attaccante[0].pg} è avvelenato e perde ~{Attaccante[0].maxhp//12} hp~", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if not Attaccante[0].area.requiem == -1:
    Attaccante[0].area.requiem = Attaccante[0].area.requiem - 1
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} Il requiem cala sulla stanza, ~{Attaccante[0].area.requiem} turni rimanenti~", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    if Attaccante[0].area.requiem == 0:
      Difensore[0].hp = 0
      Attaccante[0].hp = 0
      Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ ~ }} Il requiem oscura tutto...", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if Difensore[0].hp <= 0 or Attaccante[0].hp <= 0:
      if Difensore[0].hp <= 0 and Attaccante[0].hp <= 0:
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Defense", f"~~ }} \f\s {Attaccante[0].pg} e", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} \f\s {Difensore[0].pg} perdono coscienza...", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
      else:
       if Difensore[0].hp <= 0:
        Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} \f\s {Difensore[0].pg} perde coscienza...", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
       else:
        Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Defense", f"~~ ~ }} \f\s {Attaccante[0].pg} perde coscienza...", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
      ooc_cmd_cpg(Attaccante[0], Attaccante[0].pg, False)
      ooc_cmd_cpg(Difensore[0], Difensore[0].pg, False)
      Attaccante[0].mossa = ""
      Difensore[0].mossa = "" 
      Attaccante[0].paralisi = ""
      Difensore[0].paralisi = ""
      Attaccante[0].veleno = ""
      Difensore[0].veleno = ""
      Attaccante[0].area.ba[0] = -1
      Attaccante[0].area.requiem = -1
      Attaccante.clear()
      Difensore.clear()
  else:
       ooc_cmd_cstat(Attaccante[0], "lol")
       ooc_cmd_cstat(Difensore[0], "lol")
       Attaccante[0].mossa = ""
       Difensore[0].mossa = "" 
       t = Attaccante[0]
       Attaccante[0] = Difensore[0]
       Difensore[0] = t
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} {Attaccante[0].pg} si prepara", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }}  ad attaccare {Difensore[0].pg}", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      
   
def ooc_cmd_surrender(client, arg):
  Attaccante = client.area.Attaccante
  Difensore = client.area.Difensore
  if client in Attaccante or client in Difensore:
      if client in Difensore:
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} {Difensore[0].pg} si arrende", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      else:
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} {Attaccante[0].pg} si arrende", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      ooc_cmd_cpg(Attaccante[0], Attaccante[0].pg)
      ooc_cmd_cpg(Difensore[0], Difensore[0].pg)
      Attaccante[0].mossa = ""
      Difensore[0].mossa = "" 
      Attaccante[0].paralisi = ""
      Difensore[0].paralisi = ""
      Attaccante[0].veleno = ""
      Difensore[0].veleno = ""
      Attaccante[0].area.requiem = -1
      Attaccante.clear()
      Difensore.clear()
      client.area.ba[0] = -1
   
def ooc_cmd_remove_mov(client, arg):
  if client.pg == "":
    client.send_ooc('Devi star usando un personaggio per eliminare una sua mossa')
  else:
      j = -1
      f = open('storage/battlesystem/battlesystem.yaml', 'r') 
      lines = f.readlines()
      for line in lines:
        if f"  MovesName: {arg} {client.pg}" in line:
          j = lines.index(line)
      if not j == -1:
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       f = open('storage/battlesystem/battlesystem.yaml', 'w')
       for line in lines:
         f.write(line)
       client.send_ooc(f"{arg} eliminata!")
      else:
        client.send_ooc('Mossa non trovata!')

def ooc_cmd_remove_pg(client, arg):
  if not arg == "":
      j = -1
      f = open('storage/battlesystem/battlesystem.yaml', 'r') 
      lines = f.readlines()
      for line in lines:
        if f"Character: {arg}" in line:
          j = lines.index(line)
      if not j == -1:
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       del lines[j]
       f = open('storage/battlesystem/battlesystem.yaml', 'w')
       for line in lines:
         f.write(line)
       client.send_ooc(f"{client.pg} eliminato!")
      else:
        client.send_ooc('Mossa non trovata!')
  else:
   client.send_ooc('Per usare il comando fare /remove_pg NomePg')

def ooc_cmd_mov_list(client, arg):
  if client.pg == "":
    client.send_ooc('Devi star usando un personaggio per controllare le tue mosse')
  else:
      f = open('storage/battlesystem/battlesystem.yaml', 'r') 
      lines = f.readlines()
      msg = "\nLista mosse:\n"
      for line in lines:
        if client.pg in line:
         if not "Character:" in line:
           mov = line.split("  MovesName:")[1].split(f'{client.pg}')[0]
           msg += f"\n- {mov}"
      client.send_ooc(msg)
          
        
def ooc_cmd_showdown(client, arg):
 if not client in client.area.showdown_list:
   if not client.pg == "":
        client.area.showdown.append(client)
        client.area.showdown_list.append(client)
        client.mossa = ""
        client.paralisi = ""
        client.veleno = ""
        client.area.send_ic(None, '1', 0, "", f"../characters/{client.char_name}/default", f"~~ ~ }} {client.pg} si prepara per lo Showdown", f"{client.pos}", "", 0, -1, 0, 0, [0], client.flip, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   else:
    client.send_ooc('Devi usare un Pg per poter entrare nello Showdown!')
 else:
  client.send_ooc('Sei già entrato nello Showdown!')


def ooc_cmd_showdownatk(client, arg):
   if client in client.area.showdown:
      if not client in client.area.showdownatk:
         args = shlex.split(arg)
         f = open('storage/battlesystem/battlesystem.yaml', 'r') 
         lines = f.readlines()
         j = -1
         for line in lines:
             if f"{args[0]} {client.pg}"in line:
                 j = lines.index(line)
         if j == -1:
           client.send_ooc('Mossa non trovata')
           return
         if ": Def" in lines[j+1] or ": Spd" in lines[j+1]:
           client.send_ooc('Non puoi usare mosse difensive nello showdown')
           return
         if len(client.area.showdown)-1 == len(client.area.showdownatk):
           client.mossa = args[0]
           target = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(args[1]), False)[0] 
           if not target in client.area.showdown:
             client.send_ooc('Il bersaglio non fa parte dello showdown')
             return
           client.puntatore = target
           client.area.showdownatk.append(client)
           client.send_ooc('Mossa scelta')
           inizio_showdown(client)
         else:
           client.mossa = args[0]
           target = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(args[1]), False)[0] 
           if not target in client.area.showdown:
             client.send_ooc('Il bersaglio non fa parte dello showdown')
             return
           client.puntatore = target
           client.area.showdownatk.append(client)
           client.send_ooc('Mossa scelta')
      else:
       client.send_ooc('Hai già scelto la mossa!')
   else:
    client.send_ooc('Non sei dentro lo showdown!')

def inizio_showdown(c):
   
 f = open('storage/battlesystem/battlesystem.yaml', 'r')
 lines = f.readlines()
 for client in c.area.showdownatk:
  Attaccante = []
  Attaccante.append(client)
  Difensore = []
  Difensore.append(client.puntatore)
  for line in lines:
   if Attaccante[0].mossa in line:
     id = lines.index(line)
  ATTtipo = lines[id+1].split(": ")[1].split("\n")[0]
  ATTpotenza = float(lines[id+2].split(": ")[1].split("\n")[0])
  AttEffect = []
  AttEffect.clear()
  for i in range(3,19):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0].split('  ')[1]
           AttEffect.append(lines[id+i])
  id_char = Difensore[0].server.char_list.index(Difensore[0].char_name)
  paralyse = list(np.random.permutation(np.arange(0,len(paralisi))))
  crit = list(np.random.permutation(np.arange(0,len(critic))))
  if Attaccante[0].paralisi == "paralisi" and paralyse[0] == 2:
   Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} \f\s {Attaccante[0].pg}  è ~paralizzato~ e non riesce ad attaccare", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  else:
   if not 'AtkAll' in AttEffect:
    if not 'HAlly' in AttEffect:
     d = 1
     if ATTtipo == "Atk":
       if crit[0] == 1:
        danno = ATTpotenza*Attaccante[0].atk*d*2//(Difensore[0].defe*3)
        Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} prepara un ~attacco critico~!", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
       else:
        danno = ATTpotenza*Attaccante[0].atk*d//(Difensore[0].defe*3)
     if ATTtipo == "Spa":
      if crit[0] == 1:
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} prepara un ~attacco critico~!", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
       danno = ATTpotenza*Attaccante[0].spa*d*2//(Difensore[0].spd*3)
      else:
       danno = ATTpotenza*Attaccante[0].spa*d//(Difensore[0].spd*3)
     Difensore[0].hp = Difensore[0].hp - danno
     Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} attacca con ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     if ATTtipo == "Atk":
      Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Difensore[0].pg} perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", "{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
     else:
      Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Difensore[0].pg} perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", "{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   else:
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Attack", f"~~ }} {Attaccante[0].pg} attacca con ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    for c in Attaccante[0].area.showdown:
     if not c == Attaccante[0]:
      Difensore[0] = c
      d = 1
      if ATTtipo == "Atk":
       if crit[0] == 1:
        danno = ATTpotenza*Attaccante[0].atk*d*2//(Difensore[0].defe*3)
       else:
        danno = ATTpotenza*Attaccante[0].atk*d//(Difensore[0].defe*3)
      if ATTtipo == "Spa":
       if crit[0] == 1:
        danno = ATTpotenza*Attaccante[0].spa*d*2//(Difensore[0].spd*3)
       else:
        danno = ATTpotenza*Attaccante[0].spa*d//(Difensore[0].spd*3)
      Difensore[0].hp = Difensore[0].hp - danno
      if ATTtipo == "Atk":
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Difensore[0].pg} perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", f"{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      else:
              Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Difensore[0].pg} perde ~{danno} hp~", f"{Difensore[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", f"{id_char}^0", f"{Difensore[0].char_name}", "Defense", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Paralysis' in AttEffect:
    if not Difensore[0].paralisi == "paralisi":
       Difensore[0].paralisi = "paralisi"
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} \f\s {Difensore[0].pg} è affetto dalla paralisi per via di ~{Attaccante[0].mossa}", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Poison' in AttEffect:
    if not Difensore[0].veleno == "avvelenato":
       Difensore[0].veleno = "avvelenato"
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} \f\s  {Difensore[0].pg} è affetto dall'avvelenamento per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefDown' in AttEffect:
       Difensore[0].defe = Difensore[0].defe*0.75
       if Difensore[0].defe < 10:
         Difensore[0].defe = 10
       Attaccante[0].area.send_ic(None, '1', '-', "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} La difesa di {Difensore[0].pg} diminuisce per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkDown' in AttEffect:
       Difensore[0].atk = Difensore[0].atk*0.75
       if Difensore[0].atk < 10:
         Difensore[0].atk = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} L'attacco di {Difensore[0].pg} diminuisce per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaDown' in AttEffect:
       Difensore[0].spa = Difensore[0].spa*0.75
       if Difensore[0].spa < 10:
         Difensore[0].spa = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} L'attacco speciale di {Difensore[0].pg} diminuisce per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdDown' in AttEffect:
       Difensore[0].spd = Difensore[0].spd*0.75
       if Difensore[0].spd < 10:
         Difensore[0].spd = 10
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/Defense", f"~~ }} La difesa speciale di {Difensore[0].pg} diminuisce per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsdown", 1, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkRaise' in AttEffect:
       Attaccante[0].atk = Attaccante[0].atk*1.5
       if Attaccante[0].atk > 200:
          Attaccante[0].atk = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} L'attacco di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefRaise' in AttEffect:
       Attaccante[0].defe = Attaccante[0].defe*1.5
       if Attaccante[0].defe > 200:
          Attaccante[0].defe = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} La difesa di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaRaise' in AttEffect:
       Attaccante[0].spa = Attaccante[0].spa*1.5
       if Attaccante[0].spa > 200:
          Attaccante[0].spa = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} L'attacco speciale di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdRaise' in AttEffect:
       Attaccante[0].spd = Attaccante[0].spd*1.5
       if Attaccante[0].spd > 200:
          Attaccante[0].spd = 200
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} La difesa speciale di {Attaccante[0].pg} aumenta per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 1, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Heal' in AttEffect:
       Attaccante[0].hp = Attaccante[0].hp + Attaccante[0].maxhp//4
       if Attaccante[0].hp > Attaccante[0].maxhp:
          Attaccante[0].hp = Attaccante[0].maxhp
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} {Attaccante[0].pg} ha curato la propria vita per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'HAlly' in AttEffect:
       Difensore[0].hp = Difensore[0].hp + Difensore[0].maxhp//4
       if Difensore[0].hp > Difensore[0].maxhp:
          Difensore[0].hp = Difensore[0].maxhp
       Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} {Attaccante[0].pg} ha curato la vita di {Difensore[0].pg} per via di ~{Attaccante[0].mossa}~", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Requiem' in AttEffect:
    if Attaccante[0].area.requiem == -1:
      Attaccante[0].area.requiem = 3
      Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/default", f"~~ }} {Attaccante[0].pg} ha attivato il requiem per via di ~{Attaccante[0].mossa}~", f"{Attaccante[0].pos}", "statsup", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
 for client in Difensore[0].area.showdown:
  Attaccante[0] = client
  if Attaccante[0].veleno == "avvelenato":
    Attaccante[0].hp = Attaccante[0].hp - Attaccante[0].maxhp//12
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Attaccante[0].char_name}/Defense", f"~~ }} \f\s {Attaccante[0].pg} è avvelenato e perde ~{Attaccante[0].maxhp//12} hp~", f"{Attaccante[0].pos}", "", 0, -1, 0, 0, [0], Attaccante[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
 if not Attaccante[0].area.requiem == -1:
    Attaccante[0].area.requiem = Attaccante[0].area.requiem - 1
    Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ }} Il requiem cala sulla stanza, ~{Attaccante[0].area.requiem} turni rimanenti~", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    if Attaccante[0].area.requiem == 0:
     for client in Difensore[0].area.showdown:
      Attaccante[0] = client
      Attaccante[0].hp = 0
      Attaccante[0].area.send_ic(None, '1', 0, "", f"../characters/{Difensore[0].char_name}/default", f"~~ ~ }} Il requiem oscura tutto...", f"{Difensore[0].pos}", "statsup", 0, -1, 0, 0, [0], Difensore[0].flip, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
 Attaccante[0].area.showdownatk.clear()
 Box = []
 for c in Difensore[0].area.showdown:
   Box.append(c)
 for client in Box:
  if client.hp <= 0:
        client.area.send_ic(None, '1', 0, "", f"../characters/{client.char_name}/Defense", f"~~ }} \f\s {client.pg} perde coscienza...", f"{client.pos}", "", 0, -1, 0, 0, [0], client.flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
        client.area.showdown.remove(client)
        ooc_cmd_cpg(client, client.pg, False)
        client.mossa = ""
        client.paralisi = ""
        client.veleno = ""
 if len(client.area.showdown) == 1:
    ooc_cmd_cpg(client.area.showdown[0], client.area.showdown[0].pg, False)
    client.area.showdown[0].area.send_ic(None, '1', 0, "", f"../characters/{client.area.showdown[0].char_name}/Defense", f"~~ }} {client.area.showdown[0].pg} ha vinto lo Showdown", f"{client.area.showdown[0].pos}", "", 0, -1, 0, 0, [0], client.area.showdown[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    client.area.showdown.clear()
    Attaccante.clear()
    Difensore.clear()
    Box.clear()
    client.area.showdown_list.clear()
 else:
    client.area.showdown[0].area.send_ic(None, '1', 0, "", f"../characters/{client.area.showdown[0].char_name}/Defense", f"~~ }} Lo Showdown continua!", f"{client.area.showdown[0].pos}", "", 0, -1, 0, 0, [0], client.area.showdown[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    for c in client.area.showdown:
      ooc_cmd_showdown_list(c, "")
      ooc_cmd_cstat(c, "")
    Attaccante.clear()
    Difensore.clear()
    Box.clear()


@mod_only(hub_owners=True)
def ooc_cmd_refresh_showdown(client, arg):
    client.area.showdown.clear()
    client.area.showdownatk.clear()
    client.send_ooc('Showdown refreshato!')
    client.area.showdown_list.clear()


def ooc_cmd_showdown_list(client, arg):
    msg = "\n Lista Giocatori Showdown:\n"
    for c in client.area.showdown:
      if c in client.area.showdownatk:
          msg += f"\n [{c.id}]{c.pg} ({c.name}) ⚔️"
      else:
          msg += f"\n [{c.id}]{c.pg} ({c.name}) 🛡️"
    client.send_ooc(msg)

def ooc_cmd_showdownsurrender(client, arg):
    if client in client.area.showdown:
      client.area.showdown.remove(client)
      client.area.send_ic(None, '1', 0, "", f"../characters/{client.char_name}/Defense", f"~~ }} {client.pg} si è arreso!", f"{client.pos}", "", 0, -1, 0, 0, [0], client.flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    else:
      client.send_ooc("Non sei in partita!")
      
@mod_only(hub_owners=True)
def ooc_cmd_remove_showdown(client, arg):
    n = int(arg)
    del client.area.showdown[n]
    client.send_ooc("Fatto!")

@mod_only(hub_owners=True)
def ooc_cmd_rstat(client, arg):
 f = open('storage/battlesystem/battlesystem.yaml', 'r')
 lines = f.readlines()
 args = shlex.split(arg)
 j = -1
 for line in lines:
  if f": {args[0]}" in line:
     j = lines.index(line)
 if not j == -1:
  for arg in args:
   if "HP: " in arg:
    lines[j+3] = f"  {arg}\n"
   if "ATK: " in arg:
    lines[j+4] = f"  {arg}\n"
   if "DEF: " in arg:
    lines[j+5] = f"  {arg}\n"
   if "SPA: " in arg:
    lines[j+6] = f"  {arg}\n"
   if "SPD: " in arg:
    lines[j+7] = f"  {arg}\n"
  f = open('storage/battlesystem/battlesystem.yaml', 'w')
  for line in lines:
    f.write(line)
  f.close
 else:
  client.send_ooc('Il personaggio non è stato trovato!')       

def ooc_cmd_mov_effects(client, arg):
    client.send_ooc('AtkRaise, SpaRaise, DefRaise, SpdRaise, AtkDown, DefDown, SpdDown, SpdRaise, Heal, StealStats, Poison, Paralysis, Requiem, HAlly, AtkAll')