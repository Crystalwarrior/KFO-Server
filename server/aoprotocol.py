# tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
import re
from time import localtime, strftime
from enum import Enum

from server import commands
from server import logger
from server.exceptions import ClientError, AreaError, ArgumentError, ServerError
from server.fantacrypt import fanta_decrypt
from server.evidence import EvidenceList


class AOProtocol(asyncio.Protocol):
    """
    The main class that deals with the AO protocol.
    """

    class ArgType(Enum):
        STR = 1,
        STR_OR_EMPTY = 2,
        INT = 3

    def __init__(self, server):
        super().__init__()
        self.server = server
        self.client = None
        self.buffer = ''
        self.ping_timeout = None
        
        # Determine whether /exec is active or not and warn server owner if so.
        if getattr(commands, "ooc_cmd_exec")(self.client, "is_exec_active") == 1:
            print("""
                  
                  WARNING
                  
                  THE /exec COMMAND IN commands.py IS ACTIVE.
                  
                  UNLESS YOU ABSOLUTELY MEANT IT AND KNOW WHAT YOU ARE DOING, 
                  PLEASE STOP YOUR SERVER RIGHT NOW AND DEACTIVATE IT BY GOING TO THE
                  commands.py FILE AND FOLLOWING THE INSTRUCTIONS UNDER ooc_cmd_exec.\n
                  BAD THINGS CAN AND WILL HAPPEN OTHERWISE
                  
                  """)
        
    def data_received(self, data):
        """ Handles any data received from the network.

        Receives data, parses them into a command and passes it
        to the command handler.

        :param data: bytes of data
        """
        # try to decode as utf-8, ignore any erroneous characters
        self.buffer += data.decode('utf-8', 'ignore')
        if len(self.buffer) > 8192:
            self.client.disconnect()
        for msg in self.get_messages():
            if len(msg) < 2:
                self.client.disconnect()
                return
            # general netcode structure is not great
            if msg[0] in ('#', '3', '4'):
                if msg[0] == '#':
                    msg = msg[1:]
                spl = msg.split('#', 1)
                msg = '#'.join([fanta_decrypt(spl[0])] + spl[1:])
                logger.log_debug('[INC][RAW]{}'.format(msg), self.client)
            try:
                cmd, *args = msg.split('#')
                self.net_cmd_dispatcher[cmd](self, args)
            except KeyError:
                return

    def connection_made(self, transport):
        """ Called upon a new client connecting

        :param transport: the transport object
        """
        self.client = self.server.new_client(transport)
        self.ping_timeout = asyncio.get_event_loop().call_later(self.server.config['timeout'], self.client.disconnect)
        self.client.send_command('decryptor', 34)  # just fantacrypt things

    def connection_lost(self, exc):
        """ User disconnected

        :param exc: reason
        """
        self.server.remove_client(self.client)
        self.ping_timeout.cancel()

    def get_messages(self):
        """ Parses out full messages from the buffer.

        :return: yields messages
        """
        while '#%' in self.buffer:
            spl = self.buffer.split('#%', 1)
            self.buffer = spl[1]
            yield spl[0]
        # exception because bad netcode
        askchar2 = '#615810BC07D12A5A#'
        if self.buffer == askchar2:
            self.buffer = ''
            yield askchar2

    def validate_net_cmd(self, args, *types, needs_auth=True):
        """ Makes sure the net command's arguments match expectations.

        :param args: actual arguments to the net command
        :param types: what kind of data types are expected
        :param needs_auth: whether you need to have chosen a character
        :return: returns True if message was validated
        """
        if needs_auth and self.client.char_id == -1:
            return False
        if len(args) != len(types):
            return False
        for i, arg in enumerate(args):
            if len(arg) == 0 and types[i] != self.ArgType.STR_OR_EMPTY:
                return False
            if types[i] == self.ArgType.INT:
                try:
                    args[i] = int(arg)
                except ValueError:
                    return False
        return True

    def net_cmd_hi(self, args):
        """ Handshake.

        HI#<hdid:string>#%

        :param args: a list containing all the arguments
        """
        if not self.validate_net_cmd(args, self.ArgType.STR, needs_auth=False):
            return
        self.client.hdid = args[0]
        if self.client.hdid not in self.client.server.hdid_list:
            self.client.server.hdid_list[self.client.hdid] = []
        if self.client.ipid not in self.client.server.hdid_list[self.client.hdid]:
            self.client.server.hdid_list[self.client.hdid].append(self.client.ipid)
            self.client.server.dump_hdids()
        for ipid in self.client.server.hdid_list[self.client.hdid]:
            if self.server.ban_manager.is_banned(ipid):
                self.client.disconnect()
                return
        logger.log_server('Connected. HDID: {}.'.format(self.client.hdid), self.client)
        self.client.send_command('ID', self.client.id, self.server.software, self.server.get_version_string())
        self.client.send_command('PN', self.server.get_player_count() - 1, self.server.config['playerlimit'])
        
    def net_cmd_id(self, args):
        """ Client version and PV

        ID#<pv:int>#<software:string>#<version:string>#%

        """

        self.client.is_ao2 = False

        if len(args) < 2:
            return

        version_list = args[1].split('.')

        if len(version_list) < 3:
            return

        release = int(version_list[0])
        major = int(version_list[1])
        minor = int(version_list[2])

        if args[0] != 'AO2':
            return
        if release < 2:
            return
        elif release == 2:
            if major < 2:
                return
            elif major == 2:
                if minor < 5:
                    return

        self.client.is_ao2 = True

        self.client.send_command('FL', 'yellowtext', 'customobjections', 'flipping', 'fastloading', 'noencryption', 'deskmod', 'evidence')

    def net_cmd_ch(self, _):
        """ Periodically checks the connection.

        CHECK#%

        """
        self.client.send_command('CHECK')
        self.ping_timeout.cancel()
        self.ping_timeout = asyncio.get_event_loop().call_later(self.server.config['timeout'], self.client.disconnect)

    def net_cmd_askchaa(self, _):
        """ Ask for the counts of characters/evidence/music

        askchaa#%

        """
        char_cnt = len(self.server.char_list)
        evi_cnt = 0
        music_cnt = sum([len(x) for x in self.server.music_pages_ao1])
        self.client.send_command('SI', char_cnt, evi_cnt, music_cnt)

    def net_cmd_askchar2(self, _):
        """ Asks for the character list.

        askchar2#%

        """
        self.client.send_command('CI', *self.server.char_pages_ao1[0])

    def net_cmd_an(self, args):
        """ Asks for specific pages of the character list.

        AN#<page:int>#%

        """
        if not self.validate_net_cmd(args, self.ArgType.INT, needs_auth=False):
            return
        if len(self.server.char_pages_ao1) > args[0] >= 0:
            self.client.send_command('CI', *self.server.char_pages_ao1[args[0]])
        else:
            self.client.send_command('EM', *self.server.music_pages_ao1[0])

    def net_cmd_ae(self, _):
        """ Asks for specific pages of the evidence list.

        AE#<page:int>#%

        """
        pass  # todo evidence maybe later

    def net_cmd_am(self, args):
        """ Asks for specific pages of the music list.

        AM#<page:int>#%

        """
        if not self.validate_net_cmd(args, self.ArgType.INT, needs_auth=False):
            return
        if len(self.server.music_pages_ao1) > args[0] >= 0:
            self.client.send_command('EM', *self.server.music_pages_ao1[args[0]])
        else:
            self.client.send_done()
            self.client.send_area_list()
            self.client.send_motd()

    def net_cmd_rc(self, _):
        """ Asks for the whole character list(AO2)

        AC#%

        """

        self.client.send_command('SC', *self.server.char_list)

    def net_cmd_rm(self, _):
        """ Asks for the whole music list(AO2)

        AM#%

        """
        # Force the server to rebuild the music list, so that clients who just
        # join get the correct music list (as well as every time they request
        # an updated music list directly).
        self.server.build_music_list_ao2()
        self.client.send_command('SM', *self.server.music_list_ao2)
        

    def net_cmd_rd(self, _):
        """ Asks for server metadata(charscheck, motd etc.) and a DONE#% signal(also best packet)

        RD#%

        """

        self.client.send_done()
        if self.server.config['announce_areas']:
            if self.server.config['rp_mode_enabled']:
                self.client.send_limited_area_list()
            else:
                self.client.send_area_list()
        self.client.send_motd()
        self.client.reload_music_list() # Reload the default area's music list
        # so that it only includes areas reachable from that default area.
        
    def net_cmd_cc(self, args):
        """ Character selection.

        CC#<client_id:int>#<char_id:int>#<hdid:string>#%

        """
        if not self.validate_net_cmd(args, self.ArgType.INT, self.ArgType.INT, self.ArgType.STR, needs_auth=False):
            return
        cid = args[1]
        try:
            self.client.change_character(cid)
        except ClientError:
            return

    def net_cmd_ms(self, args):
        """ IC message.

        Refer to the implementation for details.

        """
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_host_message("You have been muted by a moderator")
            return
        if self.client.area.ic_lock and not (self.client.is_mod or self.client.is_cm or self.client.is_gm):
            self.client.send_host_message("IC chat in this area has been locked by a moderator")
            return            
        if not self.client.area.can_send_message():
            return
        if not self.validate_net_cmd(args, self.ArgType.STR, self.ArgType.STR_OR_EMPTY, self.ArgType.STR,
                                     self.ArgType.STR,
                                     self.ArgType.STR, self.ArgType.STR, self.ArgType.STR, self.ArgType.INT,
                                     self.ArgType.INT, self.ArgType.INT, self.ArgType.INT, self.ArgType.INT,
                                     self.ArgType.INT, self.ArgType.INT, self.ArgType.INT):
            return
        msg_type, pre, folder, anim, text, pos, sfx, anim_type, cid, sfx_delay, button, evidence, flip, ding, color = args
        if self.client.area.is_iniswap(self.client, pre, anim, folder) and folder != self.client.get_char_name():
            self.client.send_host_message("Iniswap is blocked in this area")
            return
        if msg_type not in ('chat', '0', '1'):
            return
        if anim_type not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
            return
        if cid != self.client.char_id:
            return
        if sfx_delay < 0:
            return
        if button not in (0, 1, 2, 3, 4, 5, 6, 7):
            return
        if evidence < 0:
            return
        if ding not in (0, 1, 2):
            return
        if color not in (0, 1, 2, 3, 4, 5, 6):
            return
        if color == 5 and not self.client.is_mod and not self.client.is_cm:
            color = 0
        if color == 6:
            text = re.sub(r'[^\x00-\x7F]+',' ', text) #remove all unicode to prevent now yellow text abuse
            if len(text.strip( ' ' )) == 1:
                color = 0
            else:
                if text.strip( ' ' ) in ('<num>', '<percent>', '<dollar>', '<and>'):
                    color = 0
        if self.client.pos:
            pos = self.client.pos
        else:
            if pos not in ('def', 'pro', 'hld', 'hlp', 'jud', 'wit'):
                return
        msg = text[:256]
        if self.client.gimp: #If you're gimped, gimp message.
            msg = self.client.gimp_message(msg)
        if self.client.disemvowel: #If you're disemvoweled, replace string.
            msg = self.client.disemvowel_message(msg)
        if self.client.remove_h: #If h is removed, replace string.
            msg = self.client.remove_h_message(msg)
        self.client.pos = pos
        if evidence:
            if self.client.area.evi_list.evidences[self.client.evi_list[evidence] - 1].pos != 'all':
                self.client.area.evi_list.evidences[self.client.evi_list[evidence] - 1].pos = 'all'
                self.client.area.broadcast_evidence_list()

        if self.client.multi_ic is None:
            self.client.area.send_command('MS', msg_type, pre, folder, anim, msg, pos, sfx, anim_type, cid,
                                      sfx_delay, button, self.client.evi_list[evidence], flip, ding, color, self.client.showname)
        else:
            for area_id in range(self.client.multi_ic[0].id, self.client.multi_ic[1].id + 1):
                target_area = self.server.area_manager.get_area_by_id(area_id)
                target_area.send_command('MS', msg_type, pre, folder, anim, msg, pos, sfx, anim_type, cid,
                                      sfx_delay, button, self.client.evi_list[evidence], flip, ding, color, self.client.showname)
                target_area.set_next_msg_delay(len(msg))
                
        self.client.area.set_next_msg_delay(len(msg))
        logger.log_server('[IC][{}][{}]{}'.format(self.client.area.id, self.client.get_char_name(), msg), self.client)

        if not self.client.is_staff() and not self.client.is_visible:
            self.client.is_visible = True
            logger.log_server('{} is no longer sneaking.'.format(self.client.ipid), self.client)
            self.client.send_host_message("You are no longer sneaking.")
            
        self.server.create_task(self.client, ['as_afk_kick', self.client.area.afk_delay, self.client.area.afk_sendto])
        if self.client.area.is_recording:
            self.client.area.recorded_messages.append(args)

    def net_cmd_ct(self, args):
        """ OOC Message

        CT#<name:string>#<message:string>#%

        """
        if self.client.is_ooc_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_host_message("You have been muted by a moderator")
            return
        if not self.validate_net_cmd(args, self.ArgType.STR, self.ArgType.STR, needs_auth=False):
            return
        if self.client.name != args[0] and self.client.fake_name != args[0]:
            if self.client.is_valid_name(args[0]):
                self.client.name = args[0]
                self.client.fake_name = args[0]
            else:
                self.client.fake_name = args[0]
                self.client.name = ''
        if self.client.name == '':
            self.client.send_host_message('You must insert a name with at least one letter')
            return
        if self.client.name.startswith(' '):
            self.client.send_host_message('You must insert a name that starts with a letter')
            return
        if self.server.config['hostname'] in self.client.name or '<dollar>G' in self.client.name:
            self.client.send_host_message('That name is reserved!')
            return
        if args[1].startswith('/'):
            spl = args[1][1:].split(' ', 1)
            cmd = spl[0]
            arg = ''
            if len(spl) == 2:
                arg = spl[1][:256]
            try:
                called_function = 'ooc_cmd_{}'.format(cmd)
                getattr(commands, called_function)(self.client, arg)
            except AttributeError:
                print('Attribute error with ' + called_function)
                self.client.send_host_message('Invalid command.')
            except (ClientError, AreaError, ArgumentError, ServerError) as ex:
                self.client.send_host_message(ex)
        else:
            if self.client.disemvowel:
                args[1] = self.client.disemvowel_message(args[1])
            self.client.area.send_command('CT', self.client.name, args[1])
            logger.log_server(
                '[OOC][{}][{}][{}]{}'.format(self.client.area.id, self.client.get_char_name(), self.client.name,
                                             args[1]), self.client)

    def net_cmd_mc(self, args):
        """ Play music.

        MC#<song_name:int>#<???:int>#%

        """
        # First attempt to switch area, because music lists typically include area names for quick access
        try:
            delimiter = args[0].find('-') 
            area = self.server.area_manager.get_area_by_name(args[0][delimiter+1:])
            self.client.change_area(area)
            
        # Otherwise, attempt to play music.
        except (AreaError, ValueError):
            if self.client.is_muted:  # Checks to see if the client has been muted by a mod
                self.client.send_host_message("You have been muted by a moderator")
                return
            if not self.client.is_dj:
                self.client.send_host_message('You were blockdj\'d by a moderator.')
                return
            if not self.validate_net_cmd(args, self.ArgType.STR, self.ArgType.INT):
                return
            if args[1] != self.client.char_id:
                return
            if self.client.change_music_cd():
                self.client.send_host_message('You changed song too many times recently. Please try again after {} seconds.'.format(int(self.client.change_music_cd())))
                return
            
            try:
                name, length = self.server.get_song_data(args[0])
                self.client.area.play_music(name, self.client.char_id, length)
                self.client.area.add_music_playing(self.client, name)
            
                logger.log_server('[{}][{}]Changed music to {}.'
                                  .format(self.client.area.id, self.client.get_char_name(), name), self.client)
                                
                if not self.client.is_staff() and not self.client.is_visible:
                    self.client.is_visible = True
                    logger.log_server('{} is no longer sneaking.'.format(self.client.ipid), self.client)
                    self.client.send_host_message("You are no longer sneaking.")
            except ServerError:
                return
        except ClientError as ex:
            self.client.send_host_message(ex)

    def net_cmd_rt(self, args):
        """ Plays the Testimony/CE animation.

        RT#<type:string>#%

        """
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_host_message("You have been muted by a moderator")
            return
        if not self.validate_net_cmd(args, self.ArgType.STR):
            return
        if args[0] not in ('testimony1', 'testimony2'):
            return
        self.client.area.send_command('RT', args[0])
        self.client.area.add_to_judgelog(self.client, 'used WT/CE')
        logger.log_server("[{}]{} Used WT/CE".format(self.client.area.id, self.client.get_char_name()), self.client)

    def net_cmd_hp(self, args):
        """ Sets the penalty bar.

        HP#<type:int>#<new_value:int>#%

        """
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_host_message("You have been muted by a moderator")
            return
        if not self.validate_net_cmd(args, self.ArgType.INT, self.ArgType.INT):
            return
        try:
            self.client.area.change_hp(args[0], args[1])
            self.client.area.add_to_judgelog(self.client, 'changed the penalties')
            logger.log_server('[{}]{} changed HP ({}) to {}'
                              .format(self.client.area.id, self.client.get_char_name(), args[0], args[1]), self.client)
        except AreaError:
            return

    def net_cmd_pe(self, args):
        """ Adds a piece of evidence.

        PE#<name: string>#<description: string>#<image: string>#%

        """
        if len(args) < 3:
            return
#        evi = Evidence(args[0], args[1], args[2], self.client.pos)
        self.client.area.evi_list.add_evidence(self.client, args[0], args[1], args[2], 'all')
        self.client.area.broadcast_evidence_list()
    
    def net_cmd_de(self, args):
        """ Deletes a piece of evidence.

        DE#<id: int>#%

        """

        self.client.area.evi_list.del_evidence(self.client, self.client.evi_list[int(args[0])])
        self.client.area.broadcast_evidence_list()

    def net_cmd_ee(self, args):
        """ Edits a piece of evidence.

        EE#<id: int>#<name: string>#<description: string>#<image: string>#%

        """

        if len(args) < 4:
            return

        evi = (args[1], args[2], args[3], 'all')

        self.client.area.evi_list.edit_evidence(self.client, self.client.evi_list[int(args[0])], evi)
        self.client.area.broadcast_evidence_list()

    def net_cmd_zz(self, _):
        """ Sent on mod call.

        """
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_host_message("You have been muted by a moderator")
            return

        if not self.client.can_call_mod():
            self.client.send_host_message("You must wait 30 seconds between mod calls.")
            return

        current_time = strftime("%H:%M", localtime())

        self.server.send_all_cmd_pred('ZZ', '[{}] {} ({}) in {} ({})'
                                      .format(current_time, self.client.get_char_name(), self.client.get_ip(), self.client.area.name,
                                              self.client.area.id), pred=lambda c: c.is_mod)
        self.client.set_mod_call_delay()
        logger.log_server('[{}][{}]{} called a moderator.'.format(self.client.get_ip(), self.client.area.id, self.client.get_char_name()))

    def net_cmd_opKICK(self, args):
        self.net_cmd_ct(['opkick', '/kick {}'.format(args[0])])

    def net_cmd_opBAN(self, args):
        self.net_cmd_ct(['opban', '/ban {}'.format(args[0])])

    net_cmd_dispatcher = {
        'HI': net_cmd_hi,  # handshake
        'ID': net_cmd_id,  # client version
        'CH': net_cmd_ch,  # keepalive
        'askchaa': net_cmd_askchaa,  # ask for list lengths
        'askchar2': net_cmd_askchar2,  # ask for list of characters
        'AN': net_cmd_an,  # character list
        'AE': net_cmd_ae,  # evidence list
        'AM': net_cmd_am,  # music list
        'RC': net_cmd_rc,  # AO2 character list
        'RM': net_cmd_rm,  # AO2 music list
        'RD': net_cmd_rd,  # AO2 done request, charscheck etc.
        'CC': net_cmd_cc,  # select character
        'MS': net_cmd_ms,  # IC message
        'CT': net_cmd_ct,  # OOC message
        'MC': net_cmd_mc,  # play song
        'RT': net_cmd_rt,  # WT/CE buttons
        'HP': net_cmd_hp,  # penalties
        'PE': net_cmd_pe,  # add evidence
        'DE': net_cmd_de,  # delete evidence
        'EE': net_cmd_ee,  # edit evidence
        'ZZ': net_cmd_zz,  # call mod button
        'opKICK': net_cmd_opKICK,  # /kick with guard on
        'opBAN': net_cmd_opBAN,  # /ban with guard on
    }
