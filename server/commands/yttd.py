import random
import asyncio
import numpy as np

from server import area
from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only
from .. import commands

__all__ = [
    'ooc_cmd_yttd',
    'ooc_cmd_yv',
    'ooc_cmd_yttd_clear',
    'ooc_cmd_yttd_list',
    'ooc_cmd_yskip',
]


yttd_list = []
lista_votanti = []
fase = []
fase.append(1)

def ooc_cmd_yttd(client, arg):
  if not client.area.partite:
   if not client in yttd_list:
      client.yttd_role = 'commoner'
      client.send_ooc('Sei stato aggiunto alla partita!')
      client.area.broadcast_ooc(f'\n[{client.id}]{client.name} si è aggiunto alla partita!\n Giocatori attuali: {len(yttd_list)+1}')
      client.yttd_clear_votare()
      client.unvotante()
      if len(yttd_list) <= 0:
              yttd_list.clear()
              client.schedule = asyncio.get_event_loop().call_later(
                60, inizio_partita)
              commands.areas.ooc_cmd_bg(client, 'YTTDCourtroom', False)
              client.area.send_ic(None, '1', 'chipslide', 'Olga Orly', 'sleeve', '~~ ~Per unirvi alla partita fare /yttd.     1 minuto rimanente', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||') 
              for c in client.area.clients:
               c.send_command('TI', 1, 2)
               c.send_command('TI', 1, 0, 60000)
       
      yttd_list.append(client)
              
   else:
      client.send_ooc('Sei già in partita!')
  else:
      client.send_ooc('La partita è già iniziata')

      

def inizio_partita():
  if len(yttd_list) > 3:
   lista_votanti.clear()
   fase[0] = 1
   lista_prov = []
   lista_prov.clear()
   for c in yttd_list:
    lista_prov.append(c)
    c.vai_skip()
    c.yttd_role = 'commoner'
    c.vai_skip()
   c.area.vai_skippabile()
   lista_prov = list(np.random.permutation(np.arange(0,len(yttd_list))))
   keymaster = yttd_list[lista_prov[1]]
   keymaster.send_ooc('Sei il keymaster')
   keymaster.yttd_role = 'keymaster'
   sage = yttd_list[lista_prov[2]]
   sage.send_ooc(f'Sei il sage, il keymaster è [{keymaster.id}]{keymaster.name}')
   sage.yttd_role = 'sage'
   sacrifice = yttd_list[lista_prov[3]]
   sacrifice.send_ooc('Sei il sacrifice')
   sacrifice.yttd_role = 'sacrifice'
   keymaster.area.partita_yttd()
   keymaster.schedule = asyncio.get_event_loop().call_later(
                600, prima_votazione)
   keymaster.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', '~~ ~Il Death Game è iniziato', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||') 
   for client in keymaster.area.clients:
               client.send_command('TI', 1, 2)
               client.send_command('TI', 1, 0, 600000)
               if not client == keymaster and not client == sage and not client == sacrifice and client in yttd_list:
                  client.send_ooc('Sei un commoner')

  else:
   for client in yttd_list: 
    try: 
     client.schedule.cancel()
    except AttributeError:
               v = 'Vabbè chissene'
   for client in lista_votanti:
         lista_votanti.clear()
   if client.area.partite:
      for c in client.area.clients:
       c.unmutare()
       try:
         c.schedule.cancel()
       except AttributeError:
               v = 'Vabbè chissene'
      c.area.unpartita_yttd()
      if len(yttd_list) > 0:
       msg = ''
       for c in yttd_list:
         msg += f'[{c.id}]{c.name} '
       c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f'~~ ~ {msg} hanno vinto!', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||') 
      c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', '~~ ~La partita è conclusa!', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||') 
   else:
    client.send_ooc('Numero di giocatori insufficienti') 
   yttd_list.clear()  
   
def prima_votazione():
   for c in yttd_list:
      c.mutare()
      lista_votanti.append(c)
   c.area.vai_unskippabile()
   c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', '~~ ~Forza votate con /yv ID', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||') 
   c.schedule = asyncio.get_event_loop().call_later(
                60, rivela_voti_prima)
   for client in c.area.clients:
               client.send_command('TI', 1, 2)
               client.send_command('TI', 1, 0, 60000)
   client.area.votazione()

def ooc_cmd_yv(client, arg):
  if client.area.votazioni:
   if client in yttd_list:
    if not client.hai_votato:
      targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False)
      for t in targets:
       if t.id == int(arg):
          target = t
      if target in lista_votanti:
       if client.yttd_role == 'sacrifice':
        target.yttd_votare(2)
       else:
        target.yttd_votare(1)
       client.send_ooc(f'Hai votato [{target.id}]{target.name}')
       client.votante()
      else:
       client.send_ooc('Giocatore non trovato!')
    else:
       client.send_ooc('Hai già votato!')
   else:
    client.send_ooc('Non stai giocando!')
  else:
     client.send_ooc('Non si può ancora votare!')

def rivela_voti_prima():
   lista_voti = []
   lista_voti.clear()
   rimossi = []
   rimossi.clear()
   for c in yttd_list:
      if c.hai_votato:
       c.area.unvotazione()
       c.unmutare()
       n = int(f'{c.vote_count}')
       lista_voti.append([n, c])
       c.unvotante()
      else:
        c.unvotante()
        rimossi.append(c)
   for c in rimossi:
        yttd_list.remove(c)
        c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f'~~ ~[{c.id}]{c.name} è stato ammazzato perchè non ha votato', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||')
   if len(yttd_list) <= 3:
     inizio_partita()
     return
   lista = []
   lista.clear()
   for j in range(16, -1, -1):
    for k in range(len(lista_voti)):
         if int(lista_voti[k][0]) == j:
           lista.append([j, lista_voti[k][1]])
   c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f'~~ ~[{lista[0][1].id}]{lista[0][1].name} voti: {lista[0][0]} [{lista[1][1].id}]{lista[1][1].name} voti: {lista[1][0]} [{lista[2][1].id}]{lista[2][1].name} voti: {lista[2][0]}', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||')
   lista_votanti.clear()
   lista_votanti.append(lista[0][1])
   lista_votanti.append(lista[1][1])
   lista_votanti.append(lista[2][1])
   c.schedule = asyncio.get_event_loop().call_later(
                30, medio_gioco)
   for client in c.area.clients:
               client.yttd_clear_votare()
               client.send_command('TI', 1, 2)
               client.send_command('TI', 1, 0, 30000)

def medio_gioco():
   fase[0] = 2
   yttd_list[1].area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f"~~ ~E' iniziata la seconda fase, pensate bene cosa fare", 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||')
   yttd_list[1].schedule = asyncio.get_event_loop().call_later(
                300, seconda_votazione)
   for client in yttd_list[1].area.clients:
               client.send_command('TI', 1, 2)
               client.send_command('TI', 1, 0, 300000)
               client.vai_skip()
   client.area.vai_skippabile()
   
def seconda_votazione():
   for c in yttd_list:
      c.mutare()
   c.area.vai_unskippabile()
   c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', '~~ ~Forza votate con /yv ID', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||') 
   c.schedule = asyncio.get_event_loop().call_later(
                60, rivela_voti_seconda)
   for client in c.area.clients:
               client.send_command('TI', 1, 2)
               client.send_command('TI', 1, 0, 60000)
   client.area.votazione()

def rivela_voti_seconda():
   lista_voti = []
   lista_voti.clear()
   rimossi = []
   rimossi.clear()
   for c in yttd_list:
      if c.hai_votato:
       c.area.unvotazione()
       c.unmutare()
       lista_voti.append([c.vote_count, c])
      else:
        rimossi.append(c)
      c.unvotante()
   for c in rimossi:
        yttd_list.remove(c) 
        c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f'~~ [{c.id}]{c.name} è stato ammazzato perchè non ha votato', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||')
   if len(yttd_list) <= 3:
     inizio_partita()
     return
   lista = []
   lista.clear()
   for j in range(16, -1, -1):
    for k in range(len(lista_voti)):
         if int(lista_voti[k][0]) == j:
           lista.append([j, lista_voti[k][1]])
   if lista[0][1].yttd_role == 'sacrifice':
     c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f'~~ ~[{lista[0][1].id}]{lista[0][1].name} era il sacrifice, ed ha vinto', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||')
     for c in yttd_list:
      c.yttd_clear_votare()
     yttd_list.clear()
   elif lista[0][1].yttd_role == 'keymaster':
     c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f'~~ ~[{lista[0][1].id}]{lista[0][1].name} era il keymaster, avete perso', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||') 
     for c in yttd_list:
      c.yttd_clear_votare()
     yttd_list.clear()  
   else:
     lista[0][1].mutare()
     lista[0][1].yttd_clear_votare()
     yttd_list.remove(lista[0][1])
     for c in yttd_list:
       c.yttd_clear_votare()
       if c.yttd_role == 'sacrifice':
          yttd_list.remove(c) 
          sacrifice = c
          sacrifice.mutare()
     c.area.send_ic(None, '0', 'chipslide', 'Olga Orly', 'sleeve', f'~~ ~[{lista[0][1].id}]{lista[0][1].name} era il {lista[0][1].yttd_role} e [{sacrifice.id}]{sacrifice.name} era il sacrifice. Hanno perso entrambi!', 'wit', '0', 0, 577, 0, '0', 0, 0, 0, 1, 'Mazziere', -1, '', 1, '0&0', 0, 0, 0, '0', 0, 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 'chipslide^(b)sleeve^(a)sleeve^', 0, '||')   
   c.schedule = asyncio.get_event_loop().call_later(
                10, inizio_partita)

@mod_only(area_owners=True)
def ooc_cmd_yttd_clear(client, arg):
   
      for c in client.area.clients:
       try:
         c.unmutare()
         c.yttd_clear_votare()
         c.schedule.cancel()
       except AttributeError:
               v = 'Vabbè chissene'
      c.area.unpartita_yttd()
      client.send_ooc('La partita è stata refreshata!')

def ooc_cmd_yttd_list(client, arg):
  if client.area.partite:
     msg = '\n===Lista giocatori===\n'
     for c in yttd_list:
      if c in lista_votanti:
        msg += f'\n[{c.id}]{c.name} ({c.char_name}) "{c.showname}" 🗳️'
      else:
        msg += f'\n[{c.id}]{c.name} ({c.char_name}) "{c.showname}"'
     client.send_ooc(msg)
  else:
     client.send_ooc('La partita non è ancora iniziata')

def ooc_cmd_yskip(client, arg):
  if client.area.partite:
    if client in yttd_list:
      if client.area.skippabile:
        if client.skip:
           client.area.count_skip()
           client.vai_unskip()
           client.area.broadcast_ooc(f'[{client.id}]{client.name} ha votato per skippare!')
           if client.area.skip_count > float(len(yttd_list))//2:
              client.area.count_unskip()
              client.area.broadcast_ooc('La discussione è stata skippata!')
              if fase[0] == 1:
                for c in client.area.clients:
                  c.vai_skip()
                  try:
                            c.schedule.cancel()
                  except AttributeError:
                    v = 'Vabbè chissene'
                prima_votazione()
              else:
                for c in client.area.clients:
                  c.vai_skip()
                  try:
                            c.schedule.cancel()
                  except AttributeError:
                    v = 'Vabbè chissene'
                seconda_votazione()
        else:
          client.send_ooc('Hai già votato per skippare')
    else:
       client.send_ooc('Non si può ancora votare per skippare')
  else:
   client.send_ooc('La partita non è iniziata')
 

def toglilo_yttd(client):
     yttd_list.remove(client)