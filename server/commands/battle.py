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
    'ooc_cmd_cbc',
    'ooc_cmd_ba',
    'ooc_cmd_am',
    'ooc_cmd_mov',
    'ooc_cmd_atk', 
    'ooc_cmd_def',
    'ooc_cmd_surrend',
    'ooc_cmd_remove_mov',
    'ooc_cmd_remove_battle_char',
    'ooc_cmd_mov_list',
    'ooc_cmd_showdown',
    'ooc_cmd_showdownatk',
    'ooc_cmd_refresh_showdown',
    'ooc_cmd_rstat',
    'ooc_cmd_showdownsurrend', 
    'ooc_cmd_remove_showdown',
    'ooc_cmd_showdown_list',
]

def ooc_cmd_cc(client, arg):
        """
        Allow you to create a battle character!
        Usage: /cc "Name" "AoCharacterName" "DefaultSprite" Hp Atk Def Spa Spd
        """
        args = shlex.split(arg)
        if int(args[3])+int(args[4])+int(args[5])+int(args[6])+int(args[7])>200:
         client.send_ooc('Your stats are too high!')
         return
        f = open('storage/battlesystem/battlesystem.yaml', 'r')
        lines = f.readlines()
        if f"Character: {args[0]}\n" in lines:
          client.send_ooc("Your char's name already exists!")
          return      
        lines.append(f'\nCharacter: {args[0]}')
        lines.append(f'\n  Sprite: {args[1]}')
        lines.append(f'\n  Default: {args[2]}')
        lines.append(f'\n  HP: {args[3]}')
        lines.append(f'\n  ATK: {args[4]}')
        lines.append(f'\n  DEF: {args[5]}')
        lines.append(f'\n  SPA: {args[6]}')
        lines.append(f'\n  SPD: {args[7]}\n =================================================================')
        f = open('storage/battlesystem/battlesystem.yaml', 'w')
        for line in lines:
           f.write(f'{line}')
        client.send_ooc(f'{args[0]} created!')

def ooc_cmd_cstat(client, arg):
  """
  Show you a character's stats.
  Usage: /cstat or /cstat CharacterName
  """
  if not arg == "":
   for hub in client.server.hub_manager.hubs:
       for area in hub.areas:
         for c in area.clients:
           if c.battle_char == arg:
              target = c
  else:
    target = client
  if not target.battle_char == "":
   msg = f"\n {target.battle_char} stats:\n\nHP: {target.hp}\nATK: {target.atk}\nDEF: {target.defe}\nSPA: {target.spa}\nSPD: {target.spd}"
   client.send_ooc(msg)
  else:
   client.send_ooc("You are not using any battle characters")
       
def ooc_cmd_cbc(client, arg, show_ic_character = True):
   """
   Allow you to choose a battle character
   Usage: /cbc Name
   """
   if not arg == "":
     f = open('storage/battlesystem/battlesystem.yaml', 'r')
     lines = f.readlines()
     personaggi = []
     j = -1
     for line in lines:
      if f"Character: {arg}\n" == line:
       j = lines.index(line)
     if not j == -1:
      charsel = lines[j+1].split(": ")[1].split("\n")[0]
      line = lines[j].split(": ")[1].split("\n")[0]
      client.battle_char = line
      client.battle_char_default = lines[j+2].split(": ")[1].split("\n")[0]
      client.hp = float(lines[j+3].split(": ")[1].split("\n")[0])
      client.maxhp = client.hp
      client.atk = float(lines[j+4].split(": ")[1].split("\n")[0])
      client.defe = float(lines[j+5].split(": ")[1].split("\n")[0])
      client.spa = float(lines[j+6].split(": ")[1].split("\n")[0])
      client.spd = float(lines[j+7].split(": ")[1].split("\n")[0])
      if show_ic_character:
       client.send_ooc(f'You have been added as {line}!')
       msg = f'{client.id} {charsel}'
       client.area.add_owner(client)
       commands.character.ooc_cmd_charselect(client, msg)
       bg = client.area.background
       client.area.remove_owner(client)
       commands.areas.ooc_cmd_bg(client, bg)
       client.send_command('MS', 1, 0, client.char_name, client.battle_char_default, "", "", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
       commands.character.ooc_cmd_pos(client, 'wit')
     else:
      client.send_ooc('Character not found')

def ooc_cmd_ba(client, arg):
 """
 Allow you to battle against an opponent
 Usage: /ba ID
 """
 Attacker = client.area.Attacker
 Defender = client.area.Defender
 if client.area.ba[0] == -1:
  if not arg == "":
     target = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(arg))
     target = target[0]
     if not client.battle_char == "" and not target.battle_char == "":
       import random
       turn = random.randint(0,1)
       if turn == 0:
        client.area.send_ic(None, '1', 0, client.char_name, client.battle_char_default, f"~~ ~ }} {client.battle_char}", f"{client.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, "", f"../misc/battle", "~~ ~ }}ATTACKS", f"{client.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, target.char_name, target.battle_char_default, f"~~ ~ }} {target.battle_char}", f"{target.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        Attacker.append(client)
        Defender.append(target)
       else:
        client.area.send_ic(None, '1', 0, target.char_name, target.battle_char_default, f"~~ ~ }} {target.battle_char}", f"{target.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, "", f"../misc/battle", "~~ ~ }}ATTACK", f"{target.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        client.area.send_ic(None, '1', 0, client.char_name, target.battle_char_default, f"~~ ~ }} {client.battle_char}", f"{client.pos}", "", 0, -1, 0, 0, [0], 0, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
        Attacker.append(target)
        Defender.append(client)
       client.area.ba[0] = 0
       Attacker[0].paralysis = ""
       Attacker[0].poison = ""
       Defender[0].paralysis = ""
       Defender[0].poison = ""
       Attacker[0].move = ""
       Defender[0].move = ""
       client.area.requiem = -1
     else:
        client.send_ooc("You did not enter the ID of the challenger correctly") 
  else:
     client.send_ooc("You did not enter the ID of the challenger correctly")
 else:
     client.send_ooc("There is already a battle")

def ooc_cmd_am(client,arg):
   """
   Allow you to create a move
   Usage: /am "NameMove" "Anim" Type Power Effects
   """
   if not arg == "":
     f = open('storage/battlesystem/battlesystem.yaml', 'r')
     lines = f.readlines()
     if f'Character: {client.battle_char}\n' in lines:
        char_i = lines.index(f'Character: {client.battle_char}\n')
        char_i = char_i+7
        args = shlex.split(arg)
        if args[2] == 'Atk' or args[2] == 'Spa':
          tot = int(args[3])+50*(len(args)-4)
          if tot > 120:
            client.send_ooc('This move is too powerful try to reduce the power or the effects!')
            return
        if args[2] == 'Def' or args[2] == 'Spd':
          tot = 50*(len(args)-3)
          if tot > 50:
           client.send_ooc('This move is too powerful try to reduce the power or the effects!')
           return
        msg = f'  MovesName: {args[0]} {client.battle_char}\n  Sprite: {args[1]}\n'    
        if args[2] == 'Atk' or args[2] == 'Def' or args[2] == 'Spa' or args[2] == 'Spd':
          msg += f'  MovesType: {args[2]}\n'
        else:
          client.send_ooc('The only types of moves are Atk Spa Def Spd')
          return
        if args[2] == 'Def' or args[2] == 'Spd':
         msg += f'  Power: 0\n'
         args[3] = 0
        else:
         if args[3].isnumeric():
          msg += f'  Power: {args[3]}\n'
         else:
          client.send_ooc('You have to put a numerical value on the move!')
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
        lines[char_i] = f'{lines[char_i]}{msg}'
        f = open('storage/battlesystem/battlesystem.yaml', 'w')
        for line in lines:
          f.write(line)
        f.close()
        ooc_cmd_mov(client, args[0])
     else:
       client.send_ooc("You didn't choose a character yet")
   else:
    client.send_ooc('You have not entered the info correctly')
                          
def ooc_cmd_mov(client, arg):
 """
 Show in ooc info about a mov
 Usage: /mov NameMove
 """
 if not arg == "":
  f = open('storage/battlesystem/battlesystem.yaml', 'r')
  lines = f.readlines()
  id = -1
  for line in lines:
   if arg in line:
     id = lines.index(line)
  if not id == -1:
   type = lines[id+2].split(": ")[1].split("\n")[0]
   power = lines[id+3].split(": ")[1].split("\n")[0]
   msg = f'\n {arg} Details:\n Type: {type}\n Power: {power}\n Effects:\n'
   for i in range(3,19):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0]
           msg += lines[id+i]
   client.send_ooc(msg)
  else:
   client.send_ooc('Move not found')
 else:
  client.send_ooc("You didn't choose any moves!")

def ooc_cmd_atk(client, arg):
 """
 When a battle starts, you can use this command to attack
 Usage: /atk MoveName
 """
 Attacker = client.area.Attacker
 Defender = client.area.Defender
 if not arg == "":
  if client in Attacker:
   if client.move == "":
     if client.area.ba[0] == 0:
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if client.battle_char in lines[id]:
       if not 'Def' in lines[id+2] and not 'Spd' in lines[id+2]:
        client.move = arg
        client.send_ooc('Move selected!')
        client.area.ba[0] = 1
       else:
        client.send_ooc('You cannot use a defensive type move to attack!')
      else:
       client.send_ooc("You cannot use a defensive type move to attack!")
     elif client.area.ba[0] == 1:
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if client.battle_char in lines[id]:
       if not 'Def' in lines[id+2] and not 'Spd' in lines[id+2]:
        client.move = arg
        client.send_ooc('Move selected!')
        battle_start(Attacker, Defender)
       else:
        client.send_ooc('You cannot use a defensive type move to attack!')
      else:
       client.send_ooc("You cannot use a defensive type move to attack!")
     else:
      client.send_ooc('No battle has started')
   else:
    client.send_ooc("You have already selected the attack!")
  else:
    client.send_ooc("You're not attacking")
 else:
   client.send_ooc('You have not selected any move')

def ooc_cmd_def(client, arg):
 """
 When a battle starts, you can use this command to defend
 Usage: /def MoveName
 """
 Attacker = client.area.Attacker
 Defender = client.area.Defender
 if not arg == "":
  if client in Defender:
   if client.move == "":
     if client.area.ba[0] == 0:
      id = -1
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if client.battle_char in lines[id]:
       if not 'Atk' in lines[id+2] and not 'Spa' in lines[id+2]:
        client.move = arg
        client.send_ooc('Move selected!')
        client.area.ba[0] = 1
       else:
        client.send_ooc("You cannot use a attack type move to defend!")
      else:
       client.send_ooc("You cannot use a move that isn't yours!")
     elif client.area.ba[0] == 1:
      f = open('storage/battlesystem/battlesystem.yaml', 'r')
      lines = f.readlines()
      id = -1
      for line in lines:
       if arg in line:
        id = lines.index(line)
      if not id == -1 and client.battle_char in lines[id]:
       if not 'Atk' in lines[id+2] and not 'Spa' in lines[id+2]:
        client.move = arg
        client.send_ooc('Move selected!')
        battle_start(Attacker, Defender)
       else:
        client.send_ooc("You cannot use a attack type move to defend!")
      else:
       client.send_ooc("You cannot use a move that isn't yours!")
     else:
      client.send_ooc('No battle has started')
   else:
    client.send_ooc("You have already selected the attack!")
  else:
    client.send_ooc("You're not defending")
 else:
   client.send_ooc('You have not selected any move')

paralysis = [1, 2, 3]
critical = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

def battle_start(Attacker, Defender):
  f = open('storage/battlesystem/battlesystem.yaml', 'r')
  lines = f.readlines()
  for line in lines:
   if Attacker[0].move in line:
     id = lines.index(line)
  ATTsprite = lines[id+1].split(": ")[1].split("\n")[0]
  ATTtype = lines[id+2].split(": ")[1].split("\n")[0]
  ATTpower = float(lines[id+3].split(": ")[1].split("\n")[0])
  AttEffect = []
  AttEffect.clear()
  for i in range(4,17):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0].split('  ')[1]
           AttEffect.append(lines[id+i])
  for line in lines:
   if Defender[0].move in line:
     id = lines.index(line)
  DEFsprite = lines[id+1].split(": ")[1].split("\n")[0]
  DEFtype = lines[id+2].split(": ")[1].split("\n")[0]
  DefEffect = []
  DefEffect.clear()
  for i in range(4,17):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0].split('  ')[1]
           DefEffect.append(lines[id+i])
  paralyse = list(np.random.permutation(np.arange(0,len(paralysis))))
  id_char = Defender[0].server.char_list.index(Defender[0].char_name)
  crit = list(np.random.permutation(np.arange(0,len(critical))))
  if Attacker[0].paralysis == "paralysis" and paralyse[0] == 2:
   Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} \f\s {Attacker[0].battle_char}  is ~paralysed~ and unable to move", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  elif Defender[0].paralysis == "paralysis" and paralyse[0] == 2:
   Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char, f"~~ }} \f\s {Defender[0].battle_char}  is ~paralysed~ and unable to move", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   Attacker[0].area.ba[0] = 0
   if ATTtype == "Atk":
    if crit[0] == 1:
     damage = ATTpower*Attacker[0].atk*4//(Defender[0].defe*3)
     Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} prepare a ~critical attack~!", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    else:
     damage = ATTpower*Attacker[0].atk*2//(Defender[0].defe*3)
   else:
    if crit[0] == 1:
     Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} prepare a ~critical attack~!", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     damage = ATTpower*Attacker[0].spa*4//(Defender[0].spd*3)
    else:
     damage = ATTpower*Attacker[0].spa*2//(Defender[0].spd*3)
   Defender[0].hp = Defender[0].hp - damage
   Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} attack with ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
   if ATTtype == "Spa":
    Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Defender[0].battle_char} is paralyzed and loses ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", f"{Defender[0].char_name}", DEFsprite, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   else:
    Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Defender[0].battle_char} is paralyzed and loses ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", f"{Defender[0].char_name}", DEFsprite, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  else:
   d = 1
   if (ATTtype == "Atk" and DEFtype == "Def") or (ATTtype == "Spa" and DEFtype == "Spd"):
    d = 0.5
   if ATTtype == "Atk":
    if crit[0] == 1:
     Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} prepare a ~critical attack~!", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     damage = ATTpower*Attacker[0].atk*d*2//(Defender[0].defe*3)
    else:
     damage = ATTpower*Attacker[0].atk*d//(Defender[0].defe*3)
   if ATTtype == "Spa":
    if crit[0] == 1:
     Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} prepare a ~critical attack~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     damage = ATTpower*Attacker[0].spa*d*2//(Defender[0].spd*3)
    else:
     damage = ATTpower*Attacker[0].spa*d//(Defender[0].spd*3)
   if not damage == 0:
    Defender[0].hp = Defender[0].hp - damage
    Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} attack with ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    if ATTtype == "Atk": 
     Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Defender[0].battle_char} defends with ~{Defender[0].move}~, but lose ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", f"{Defender[0].char_name}", DEFsprite, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    else:
     Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Defender[0].battle_char} defends with ~{Defender[0].move}~, but lose ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", f"{Defender[0].char_name}", DEFsprite, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    Attacker[0].area.ba[0] = 0
   else:
    Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} use ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    Attacker[0].area.ba[0] = 0
   if 'Paralysis' in AttEffect:
    if not Defender[0].paralysis == "paralysis":
       Defender[0].paralysis = "paralysis"
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} \f\s {Defender[0].battle_char} is suffering from paralysis due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Poison' in AttEffect:
    if not Defender[0].poison == "poison":
       Defender[0].poison = "poison"
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} \f\s  {Defender[0].battle_char} is suffering from poisoning because of ~{Attacker[0].move}~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefDown' in AttEffect:
       Defender[0].defe = Defender[0].defe*0.75
       if Defender[0].defe < 10:
         Defender[0].defe = 10
       Attacker[0].area.send_ic(None, '1', '-', Defender[0].char_name, DEFsprite, f"~~ }} The defense of {Defender[0].battle_char} decreases due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkDown' in AttEffect:
       Defender[0].atk = Defender[0].atk*0.75
       if Defender[0].atk < 10:
         Defender[0].atk = 10
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The attack {Defender[0].battle_char} decreases due to  ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaDown' in AttEffect:
       Defender[0].spa = Defender[0].spa*0.75
       if Defender[0].spa < 10:
         Defender[0].spa = 10
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The special attack of {Defender[0].battle_char} decreases due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdDown' in AttEffect:
       Defender[0].spd = Defender[0].spd*0.75
       if Defender[0].spd < 10:
         Defender[0].spd = 10
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The special defense of {Defender[0].battle_char} decreases due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkRaise' in AttEffect:
       Attacker[0].atk = Attacker[0].atk*1.5
       if Attacker[0].atk > 200:
          Attacker[0].atk = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The attack of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefRaise' in AttEffect:
       Attacker[0].defe = Attacker[0].defe*1.5
       if Attacker[0].defe > 200:
          Attacker[0].defe = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The defense of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaRaise' in AttEffect:
       Attacker[0].spa = Attacker[0].spa*1.5
       if Attacker[0].spa > 200:
          Attacker[0].spa = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The special attack of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdRaise' in AttEffect:
       Attacker[0].spd = Attacker[0].spd*1.5
       if Attacker[0].spd > 200:
          Attacker[0].spd = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The special defense of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Heal' in AttEffect:
       Attacker[0].hp = Attacker[0].hp + Attacker[0].maxhp//4
       if Attacker[0].hp > Attacker[0].maxhp:
          Attacker[0].hp = Attacker[0].maxhp
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} {Attacker[0].battle_char} recover {Attacker[0].maxhp//4} with ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'StealStat' in AttEffect:
       Attacker[0].atk = Defender[0].atk
       Attacker[0].defe = Defender[0].defe
       Attacker[0].spa = Defender[0].spa
       Attacker[0].spd = Defender[0].spd
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} {Attacker[0].battle_char} stole the opponent's increased stats because of ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Requiem' in AttEffect:
    if Attacker[0].area.requiem == -1:
      Attacker[0].area.requiem = 3
      Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} {Attacker[0].battle_char} activated the requiem because of ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Paralysis' in DefEffect:
    if not Attacker[0].paralysis == "paralysis":
       Attacker[0].paralysis = "paralysis"
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} \f\s {Attacker[0].battle_char} is paralysed due to ~{Defender[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Poison' in DefEffect:
    if not Attacker[0].poison == "poison":
       Attacker[0].poison = "poison"
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} \f\s  {Attacker[0].battle_char} is poisoned due to ~{Defender[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefDown' in DefEffect:
       Attacker[0].defe = Attacker[0].defe*0.75
       if Attacker[0].defe < 10:
          Attacker[0].defe = 10
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The defense of {Attacker[0].battle_char} decreases due to ~{Defender[0].move}~", f"{Attacker[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkDown' in DefEffect:
       Attacker[0].atk = Attacker[0].atk*0.75
       if Attacker[0].atk < 10:
          Attacker[0].atk = 10
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The attack of {Attacker[0].battle_char} decreases due to ~{Defender[0].move}~", f"{Attacker[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaDown' in DefEffect:
       Attacker[0].spa = Attacker[0].spa*0.75
       if Attacker[0].spa < 10:
          Attacker[0].spa = 10
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The special attack {Attacker[0].battle_char} decreases due to ~{Defender[0].move}~", f"{Attacker[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdDown' in DefEffect:
       Attacker[0].spd = Attacker[0].spd*0.75
       if Attacker[0].spd < 10:
          Attacker[0].spd = 10
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The special defense of {Attacker[0].battle_char} decreases due to ~{Defender[0].move}~", f"{Attacker[0].pos}", "statsdown", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkRaise' in DefEffect:
       Defender[0].atk = Defender[0].atk*1.5
       if Defender[0].atk > 200:
          Defender[0].atk = 200
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The attack of {Defender[0].battle_char} increases due to ~{Defender[0].move}~", f"{Defender[0].pos}", "statsup", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefRaise' in DefEffect:
       Defender[0].defe = Defender[0].defe*1.5
       if Defender[0].defe > 200:
          Defender[0].defe = 200
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The defense of {Defender[0].battle_char} increases due to ~{Defender[0].move}~", f"{Defender[0].pos}", "statsup", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaRaise' in DefEffect:
       Defender[0].spa = Defender[0].spa*1.5
       if Defender[0].spa > 200:
          Defender[0].spa = 200
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The special attack of {Defender[0].battle_char} increases due to ~{Defender[0].move}~", f"{Defender[0].pos}", "statsup", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdRaise' in DefEffect:
       Defender[0].spd = Defender[0].spd*1.5
       if Defender[0].spd > 200:
          Defender[0].spd = 200
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The special defense of {Defender[0].battle_char} increases due to ~{Defender[0].move}~", f"{Defender[0].pos}", "statsup", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Heal' in DefEffect:
       Defender[0].hp = Defender[0].hp + Defender[0].maxhp//4
       if Defender[0].hp > Defender[0].maxhp:
          Defender[0].hp = Defender[0].maxhp
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} {Defender[0].battle_char} recover {Defender[0].maxhp//4} with ~{Defender[0].mossa}~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'StealStat' in DefEffect:
       Defender[0].atk = Defender[0].atk
       Defender[0].defe = Defender[0].defe
       Defender[0].spa = Defender[0].spa
       Defender[0].spd = Defender[0].spd
       Defender[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} {Defender[0].battle_char} stole the opponent's increased stats because of ~{Defender[0].move}~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Requiem' in DefEffect:
     if Attacker[0].area.requiem == -1:
      Attacker[0].area.requiem = 3
      Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} {Defender[0].battle_char} activated the requiem because of ~{Defender[0].move}~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if Defender[0].poison == "poison":
    Defender[0].hp = Defender[0].hp - Defender[0].maxhp//12
    Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} \f\s {Defender[0].battle_char} is poisoned and lose ~{Defender[0].maxhp//12} hp~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if Attacker[0].poison == "poison":
    Attacker[0].hp = Attacker[0].hp - Attacker[0].maxhp//12
    Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, DEFsprite, f"~~ }} \f\s {Attacker[0].battle_char} is poisoned and lose ~{Attacker[0].maxhp//12} hp~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if not Attacker[0].area.requiem == -1:
    Attacker[0].area.requiem = Attacker[0].area.requiem - 1
    Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ }} The requiem has been activated, ~{Attacker[0].area.requiem} remaining turns~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    if Attacker[0].area.requiem == 0:
      Defender[0].hp = 0
      Attacker[0].hp = 0
      Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, DEFsprite, f"~~ ~ }} The requiem obscures everything...", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  if Defender[0].hp <= 0 or Attacker[0].hp <= 0:
      if Defender[0].hp <= 0 and Attacker[0].hp <= 0:
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} \f\s {Attacker[0].battle_char} and", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} \f\s {Defender[0].battle_char} have fainted...", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
      else:
       if Defender[0].hp <= 0:
        Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} \f\s {Defender[0].battle_char} has fainted...", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
       else:
        Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Defender[0].battle_char_default, f"~~ ~ }} \f\s {Attacker[0].battle_char} has fainted...", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
      ooc_cmd_cbc(Attacker[0], Attacker[0].battle_char, False)
      ooc_cmd_cbc(Defender[0], Defender[0].battle_char, False)
      Attacker[0].move = ""
      Defender[0].move = "" 
      Attacker[0].paralysis = ""
      Defender[0].paralysis = ""
      Attacker[0].poison = ""
      Defender[0].poison = ""
      Attacker[0].area.ba[0] = -1
      Attacker[0].area.requiem = -1
      Attacker.clear()
      Defender.clear()
  else:
       ooc_cmd_cstat(Attacker[0], "")
       ooc_cmd_cstat(Defender[0], "")
       Attacker[0].move = ""
       Defender[0].move = "" 
       t = Attacker[0]
       Attacker[0] = Defender[0]
       Defender[0] = t
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} {Attacker[0].battle_char} gets ready", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }}  to attack {Defender[0].battle_char}", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      
def ooc_cmd_surrend(client, arg):
  """
  When you are in a battle, you can use this command to surrend
  Usage: /surrend
  """
  Attacker = client.area.Attacker
  Defender = client.area.Defender
  if client in Attacker or client in Defender:
      if client in Defender:
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} {Defender[0].battle_char} gives up", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      else:
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Defender[0].battle_char_default, f"~~ }} {Attacker[0].battle_char} gives up", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      ooc_cmd_cbc(Attacker[0], Attacker[0].battle_char, False)
      ooc_cmd_cbc(Defender[0], Defender[0].battle_char, False)
      Attacker[0].move = ""
      Defender[0].move = "" 
      Attacker[0].paralysis = ""
      Defender[0].paralysis = ""
      Attacker[0].poison = ""
      Defender[0].poison = ""
      Attacker[0].area.requiem = -1
      Attacker.clear()
      Defender.clear()
      client.area.ba[0] = -1
   
def ooc_cmd_remove_mov(client, arg):
  """
  You can use this command to remove a move in move list.
  Usage: /remove_mov NameMove
  """
  if client.battle_char == "":
    client.send_ooc('You must be using a character to eliminate a move from it')
  else:
      id = -1
      f = open('storage/battlesystem/battlesystem.yaml', 'r') 
      lines = f.readlines()
      for line in lines:
        if f"  MovesName: {arg} {client.battle_char}" in line:
          id = lines.index(line)
      if not id == -1:
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       f = open('storage/battlesystem/battlesystem.yaml', 'w')
       for line in lines:
         f.write(line)
       client.send_ooc(f"{arg} eliminated!")
      else:
        client.send_ooc('Move not found!')

def ooc_cmd_remove_battle_char(client, arg):
  """
  You can use this command to remove a battle character from the list
  Usage: /remove_battle_char NameBattleChar
  """
  if not arg == "":
      id = -1
      f = open('storage/battlesystem/battlesystem.yaml', 'r') 
      lines = f.readlines()
      for line in lines:
        if f"Character: {arg}" in line:
          id = lines.index(line)
      if not id == -1:
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       del lines[id]
       f = open('storage/battlesystem/battlesystem.yaml', 'w')
       for line in lines:
         f.write(line)
       client.send_ooc(f"{arg} eliminated!")
      else:
        client.send_ooc('Move not found!')
  else:
   client.send_ooc('To use the command do /remove_pg namecharacter')

def ooc_cmd_mov_list(client, arg):
  """
  You can use this command to show your move list
  Usage: /mov_list
  """
  if client.battle_char == "":
    client.send_ooc('You must be using a character to check his moves')
  else:
      f = open('storage/battlesystem/battlesystem.yaml', 'r') 
      lines = f.readlines()
      msg = "\nMoves list:\n"
      for line in lines:
        if client.battle_char in line:
         if not "Character:" in line and not "Sprite:" in line:
           mov = line.split('MovesName:')[1].split(f'{client.battle_char}')[0]
           msg += f"\n- {mov}"
      client.send_ooc(msg)
           
def ooc_cmd_showdown(client, arg):
 """
 Allow you to battle against more opponents
 Usage: /showdown
 """
 if not client in client.area.showdown_list:
   if not client.battle_char == "":
        client.area.showdown.append(client)
        client.area.showdown_list.append(client)
        client.move = ""
        client.paralysis = ""
        client.poison = ""
        client.area.send_ic(None, '1', 0, client.char_name, client.battle_char_default, f"~~ ~ }} {client.battle_char} gets ready for the Showdown", f"{client.pos}", "", 0, -1, 0, 0, [0], client.flip, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   else:
    client.send_ooc('You must use a character to be able to enter the Showdown!')
 else:
  client.send_ooc('You have already entered the Showdown!')

def ooc_cmd_showdownatk(client, arg):
 """
 When a showdown starts, you can use this command to attack
 Usage: /showdownatk MoveName IDtarget
 """
   if client in client.area.showdown:
      if not client in client.area.showdownatk:
         args = shlex.split(arg)
         f = open('storage/battlesystem/battlesystem.yaml', 'r') 
         lines = f.readlines()
         id = -1
         for line in lines:
             if f"{args[0]} {client.battle_char}"in line:
                 id = lines.index(line)
         if id == -1:
           client.send_ooc('Move not found')
           return
         if ": Def" in lines[id+2] or ": Spd" in lines[id+2]:
           client.send_ooc('You cannot use defensive moves in the Showdown')
           return
         if len(client.area.showdown)-1 == len(client.area.showdownatk):
           client.move = args[0]
           target = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(args[1]), False)[0] 
           if not target in client.area.showdown:
             client.send_ooc('The target is not part of the Showdown')
             return
           client.battle_target = target
           client.area.showdownatk.append(client)
           client.send_ooc('Move selected')
           showdown_start(client)
         else:
           client.move = args[0]
           target = client.server.client_manager.get_targets(client, TargetType.ID,
                                                            int(args[1]), False)[0] 
           if not target in client.area.showdown:
             client.send_ooc('The target is not part of the Showdown')
             return
           client.battle_target = target
           client.area.showdownatk.append(client)
           client.send_ooc('Move selected')
      else:
       client.send_ooc('You have already chosen the move!')
   else:
    client.send_ooc('You are not in the Showdown!')

def showdown_start(c):
   
 f = open('storage/battlesystem/battlesystem.yaml', 'r')
 lines = f.readlines()
 for client in c.area.showdownatk:
  Attacker = []
  Attacker.append(client)
  Defender = []
  Defender.append(client.battle_target)
  for line in lines:
   if Attacker[0].move in line:
     id = lines.index(line)
  ATTsprite = lines[id+1].split(": ")[1].split("\n")[0]
  ATTtype = lines[id+2].split(": ")[1].split("\n")[0]
  ATTpower = float(lines[id+3].split(": ")[1].split("\n")[0])
  AttEffect = []
  AttEffect.clear()
  for i in range(4,19):
         if 'Yes' in lines[id+i]:
           lines[id+i] = lines[id+i].split(':')[0].split('  ')[1]
           AttEffect.append(lines[id+i])
  id_char = Defender[0].server.char_list.index(Defender[0].char_name)
  paralyse = list(np.random.permutation(np.arange(0,len(paralysis))))
  crit = list(np.random.permutation(np.arange(0,len(critical))))
  if Attacker[0].paralysis == "paralysis" and paralyse[0] == 2:
   Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} \f\s {Attacker[0].battle_char} is ~paralysed~ and unable to move", "", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
  else:
   if not 'AtkAll' in AttEffect:
    if not 'HAlly' in AttEffect:
     d = 1
     if ATTtype == "Atk":
       if crit[0] == 1:
        damage = ATTpower*Attacker[0].atk*d*2//(Defender[0].defe*3)
        Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} prepare a ~critical attack~!", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
       else:
        damage = ATTpower*Attacker[0].atk*d//(Defender[0].defe*3)
     if ATTtype == "Spa":
      if crit[0] == 1:
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} prepare a ~critical attack~!", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
       damage = ATTpower*Attacker[0].spa*d*2//(Defender[0].spd*3)
      else:
       damage = ATTpower*Attacker[0].spa*d//(Defender[0].spd*3)
     Defender[0].hp = Defender[0].hp - damage
     Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} attack with ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
     if ATTtype == "Atk":
      Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Defender[0].battle_char} lose ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", Defender[0].char_name, Defender[0].battle_char_default, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
     else:
      Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Defender[0].battle_char} lose ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", Defender[0].char_name, Defender[0].battle_char_default, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   else:
    Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, ATTsprite, f"~~ }} {Attacker[0].battle_char} attack with ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    for c in Attacker[0].area.showdown:
     if not c == Attacker[0]:
      Defender[0] = c
      d = 1
      if ATTtype == "Atk":
       if crit[0] == 1:
        damage = ATTpower*Attacker[0].atk*d*2//(Defender[0].defe*3)
       else:
        damage = ATTpower*Attacker[0].atk*d//(Defender[0].defe*3)
      if ATTtype == "Spa":
       if crit[0] == 1:
        damage = ATTpower*Attacker[0].spa*d*2//(Defender[0].spd*3)
       else:
        damage = ATTpower*Attacker[0].spa*d//(Defender[0].spd*3)
      Defender[0].hp = Defender[0].hp - damage
      if ATTtype == "Atk":
       Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Attack", f"~~ }} \f\s {Defender[0].battle_char} lose ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_atk", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", f"{Defender[0].char_name}", Defender[0].battle_char_default, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
      else:
       Attacker[0].area.send_ic(None, '1', 0, "", f"../characters/Battle/anim/Specialattack", f"~~ }} \f\s {Defender[0].battle_char} lose ~{damage} hp~", f"{Defender[0].pos}", "battlesystem_spa", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", f"{id_char}^0", f"{Defender[0].char_name}", Defender[0].battle_char_default, 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Paralysis' in AttEffect:
    if not Defender[0].paralysis == "paralysis":
       Defender[0].paralysis = "paralysis"
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} \f\s {Defender[0].battle_char} is suffering from paralysis due to ~{Attacker[0].move}", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Poison' in AttEffect:
    if not Defender[0].poison == "poison":
       Defender[0].poison = "poison"
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} \f\s  {Defender[0].battle_char} is suffering from poisoning because of ~{Attacker[0].move}~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefDown' in AttEffect:
       Defender[0].defe = Defender[0].defe*0.75
       if Defender[0].defe < 10:
         Defender[0].defe = 10
       Attacker[0].area.send_ic(None, '1', '-', Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} The defense of {Defender[0].battle_char} decreases due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkDown' in AttEffect:
       Defender[0].atk = Defender[0].atk*0.75
       if Defender[0].atk < 10:
         Defender[0].atk = 10
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} The attack of {Defender[0].battle_char} decreases due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaDown' in AttEffect:
       Defender[0].spa = Defender[0].spa*0.75
       if Defender[0].spa < 10:
         Defender[0].spa = 10
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} The special attack of {Defender[0].battle_char} decreases due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdDown' in AttEffect:
       Defender[0].spd = Defender[0].spd*0.75
       if Defender[0].spd < 10:
         Defender[0].spd = 10
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} The special defense of {Defender[0].battle_char} decreases due to ~{Attacker[0].move}~", f"{Defender[0].pos}", "statsdown", 1, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsdown", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'AtkRaise' in AttEffect:
       Attacker[0].atk = Attacker[0].atk*1.5
       if Attacker[0].atk > 200:
          Attacker[0].atk = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The attack of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'DefRaise' in AttEffect:
       Attacker[0].defe = Attacker[0].defe*1.5
       if Attacker[0].defe > 200:
          Attacker[0].defe = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The defense of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpaRaise' in AttEffect:
       Attacker[0].spa = Attacker[0].spa*1.5
       if Attacker[0].spa > 200:
          Attacker[0].spa = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The special attack of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'SpdRaise' in AttEffect:
       Attacker[0].spd = Attacker[0].spd*1.5
       if Attacker[0].spd > 200:
          Attacker[0].spd = 200
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} The special defense of {Attacker[0].battle_char} increases due to ~{Attacker[0].move}~", f"{Attacker[0].pos}", "statsup", 1, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", "280^0", "Battle", "anim/Statsup", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Heal' in AttEffect:
       Attacker[0].hp = Attacker[0].hp + Attacker[0].maxhp//4
       if Attacker[0].hp > Attacker[0].maxhp:
          Attacker[0].hp = Attacker[0].maxhp
       Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} {Attacker[0].battle_char} recover {Attacker[0].maxhp//4} with ~{Attacker[0].mossa}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'HAlly' in AttEffect:
       Defender[0].hp = Defender[0].hp + Defender[0].maxhp//4
       if Defender[0].hp > Defender[0].maxhp:
          Defender[0].hp = Defender[0].maxhp
       Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} {Attacker[0].battle_char} heals {Defender[0].battle_char} by {Defender[0].maxhp//4} with ~{Attacker[0].move}~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
   if 'Requiem' in AttEffect:
    if Attacker[0].area.requiem == -1:
      Attacker[0].area.requiem = 3
      Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} {Attaccker[0].battle_char} activated the requiem because of ~{Attacker[0].move}~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
 for client in Defender[0].area.showdown:
  Attacker[0] = client
  if Attacker[0].poison == "poison":
    Attacker[0].hp = Attacker[0].hp - Attacker[0].maxhp//12
    Attacker[0].area.send_ic(None, '1', 0, Attacker[0].char_name, Attacker[0].battle_char_default, f"~~ }} \f\s {Attacker[0].battle_char} is poisoned and lose ~{Attacker[0].maxhp//12} hp~", f"{Attacker[0].pos}", "", 0, -1, 0, 0, [0], Attacker[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
 if not Attacker[0].area.requiem == -1:
    Attacker[0].area.requiem = Attacker[0].area.requiem - 1
    Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ }} The requiem has been activated, ~{Attacker[0].area.requiem} remaining turns~", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
    if Attacker[0].area.requiem == 0:
     for client in Defender[0].area.showdown:
      Attacker[0] = client
      Attacker[0].hp = 0
      Attacker[0].area.send_ic(None, '1', 0, Defender[0].char_name, Defender[0].battle_char_default, f"~~ ~ }} The requiem obscures everything......", f"{Defender[0].pos}", "", 0, -1, 0, 0, [0], Defender[0].flip, 0, 0, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "")
 Attacker[0].area.showdownatk.clear()
 new_showdown_list = []
 for c in Defender[0].area.showdown:
   new_showdown_list.append(c)
 for client in new_showdown_list:
  if client.hp <= 0:
        client.area.send_ic(None, '1', 0, client.char_name, client.battle_char_default, f"~~ }} \f\s {client.battle_char} has fainted...", f"{client.pos}", "", 0, -1, 0, 0, [0], client.flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
        client.area.showdown.remove(client)
        ooc_cmd_cbc(client, client.battle_char, False)
        client.move = ""
        client.paralysis = ""
        client.poison = ""
 if len(client.area.showdown) == 1:
    ooc_cmd_cbc(client.area.showdown[0], client.area.showdown[0].battle_char, False)
    client.area.showdown[0].area.send_ic(None, '1', 0, client.area.showdown[0].char_name, client.area.showdown[0].battle_char_default, f"~~ }} {client.area.showdown[0].battle_char} won the Showdown", f"{client.area.showdown[0].pos}", "", 0, -1, 0, 0, [0], client.area.showdown[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    client.area.showdown.clear()
    Attacker.clear()
    Defender.clear()
    new_showdown_list.clear()
    client.area.showdown_list.clear()
 else:
    client.area.showdown[0].area.send_ic(None, '1', 0, client.area.showdown[0].char_name, client.area.showdown[0].battle_char_default, f"~~ }} The Showdown continues!", f"{client.area.showdown[0].pos}", "", 0, -1, 0, 0, [0], client.area.showdown[0].flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    for c in client.area.showdown:
      ooc_cmd_showdown_list(c, "")
      ooc_cmd_cstat(c, "")
    Attacker.clear()
    Defender.clear()
    new_showdown_list.clear()


@mod_only(hub_owners=True)
def ooc_cmd_refresh_showdown(client, arg):
    """
    Refresh a showdown
    Usage: /refresh_showdown
    """
    client.area.showdown.clear()
    client.area.showdownatk.clear()
    client.send_ooc('Showdown refreshed!')
    client.area.showdown_list.clear()


def ooc_cmd_showdown_list(client, arg):
    """
    Show you the showdown player list
    Usage: /showdown_list
    """
    msg = "\n Showdown Player List:\n"
    for c in client.area.showdown:
      if c in client.area.showdownatk:
          msg += f"\n [{c.id}]{c.battle_char} ({c.name}) ⚔️"
      else:
          msg += f"\n [{c.id}]{c.battle_char} ({c.name}) 🛡️"
    client.send_ooc(msg)

def ooc_cmd_showdownsurrend(client, arg):
  """
  When you are in a showdown, you can use this command to surrend
  Usage: /showdownsurrend
  """
    if client in client.area.showdown:
      client.area.showdown.remove(client)
      client.area.send_ic(None, '1', 0, client.char_name, client.battle_char_default, f"~~ }} {client.battle_char} gave up!", f"{client.pos}", "", 0, -1, 0, 0, [0], client.flip, 0, 8, " ", -1, "", "", 0, 0, 0, 0, "0", 0, "", "", "", 0, "") 
    else:
      client.send_ooc("You are not in game!")
      
@mod_only(hub_owners=True)
def ooc_cmd_remove_showdown(client, arg):
    """
    Allow you to remove a player from a showdown
    Usage: /remove_showdown IDShowdownlist
    """
    n = int(arg)
    del client.area.showdown[n]
    client.send_ooc("Done!")

@mod_only(hub_owners=True)
def ooc_cmd_rstat(client, arg):
 """
 Allow you to modify the player's stats
 Usage: /rstat STATS: N  es. /rstat HP: 60
 """
 f = open('storage/battlesystem/battlesystem.yaml', 'r')
 lines = f.readlines()
 args = shlex.split(arg)
 id = -1
 for line in lines:
  if f": {args[0]}" in line:
     id = lines.index(line)
 if not id == -1:
  for arg in args:
   if "HP: " in arg:
    lines[id+3] = f"  {arg}\n"
   if "ATK: " in arg:
    lines[id+4] = f"  {arg}\n"
   if "DEF: " in arg:
    lines[id+5] = f"  {arg}\n"
   if "SPA: " in arg:
    lines[id+6] = f"  {arg}\n"
   if "SPD: " in arg:
    lines[id+7] = f"  {arg}\n"
  f = open('storage/battlesystem/battlesystem.yaml', 'w')
  for line in lines:
    f.write(line)
  f.close()
 else:
  client.send_ooc('Character not found!')       

def ooc_cmd_mov_effects(client, arg):
    """
    Show you in ooc all Move's Effects
    Usage: /mov_effects
    """
    client.send_ooc('AtkRaise, SpaRaise, DefRaise, SpdRaise, AtkDown, DefDown, SpdDown, SpdRaise, Heal, StealStats, Poison, Paralysis, Requiem, HAlly, AtkAll')
