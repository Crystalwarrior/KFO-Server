# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-19 Chrezm/Iuvee <thechrezm@gmail.com>
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import asyncio
import re

from time import localtime, strftime

from server import logger
from server.constants import ArgType, Clients, Constants
from server.exceptions import AreaError, ClientError, ServerError, PartyError, TsuserverException
from server.fantacrypt import fanta_decrypt
from server.evidence import EvidenceList

class AOProtocol(asyncio.Protocol):
    """
    The main class that deals with the AO protocol.
    """

    def __init__(self, server):
        super().__init__()
        self.server = server
        self.client = None
        self.buffer = ''
        self.ping_timeout = None
        logger.log_print = logger.log_print2 if self.server.in_test else logger.log_print

        # Determine whether /exec is active or not and warn server owner if so.
        if getattr(self.server.commands, "ooc_cmd_exec")(self.client, "is_exec_active") == 1:
            logger.log_print("""

                  WARNING

                  THE /exec COMMAND IN commands.py IS ACTIVE.

                  UNLESS YOU ABSOLUTELY MEANT IT AND KNOW WHAT YOU ARE DOING,
                  PLEASE STOP YOUR SERVER RIGHT NOW AND DEACTIVATE IT BY GOING TO THE
                  commands.py FILE AND FOLLOWING THE INSTRUCTIONS UNDER ooc_cmd_exec.\n
                  BAD THINGS CAN AND WILL HAPPEN OTHERWISE.

                  """)

    def data_received(self, data):
        """ Handles any data received from the network.

        Receives data, parses them into a command and passes it
        to the command handler.

        :param data: bytes of data
        """
        buf = data
        if buf is None:
            buf = b''
        # try to decode as utf-8, ignore any erroneous characters
        self.buffer += buf.decode('utf-8', 'ignore')
        self.buffer = self.buffer.translate({ord(c): None for c in '\0'})

        if len(self.buffer) > 8192:
            msg = self.buffer if len(self.buffer) < 512 else self.buffer[:512] + '...'
            logger.log_server('Terminated {} (packet too long): sent {} ({} bytes)'
                              .format(self.client.get_ipreal(), msg, len(self.buffer)))
            self.client.disconnect()
            return

        found_message = False
        for msg in self.get_messages():
            found_message = True
            if len(msg) < 2:
                # This immediatelly kills any client that does not even try to follow the proper
                # client protocol
                msg = self.buffer if len(self.buffer) < 512 else self.buffer[:512] + '...'
                logger.log_server('Terminated {} (packet too short): sent {} ({} bytes)'
                                  .format(self.client.get_ipreal(), msg, len(self.buffer)))
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
                # print(f'> {self.client.id}: {msg}')
                cmd, *args = msg.split('#')
                self.net_cmd_dispatcher[cmd](self, args)
            except Exception as ex:
                self.server.send_error_report(self.client, cmd, args, ex)
        if not found_message:
            # This immediatelly kills any client that does not even try to follow the proper
            # client protocol
            msg = self.buffer if len(self.buffer) < 512 else self.buffer[:512] + '...'
            logger.log_server('Terminated {} (packet syntax unrecognized): sent {} ({} bytes)'
                              .format(self.client.get_ipreal(), msg, len(self.buffer)))
            self.client.disconnect()

    def connection_made(self, transport, my_protocol=None):
        """ Called upon a new client connecting

        :param transport: the transport object
        """
        self.client = self.server.new_client(transport, my_protocol=my_protocol)
        self.ping_timeout = asyncio.get_event_loop().call_later(self.server.config['timeout'], self.client.disconnect)
        self.client.send_command('decryptor', 34)  # just fantacrypt things

    def connection_lost(self, exc, client=None):
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
            if len(arg) == 0 and types[i] != ArgType.STR_OR_EMPTY:
                return False
            if types[i] == ArgType.INT:
                try:
                    args[i] = int(arg)
                except ValueError:
                    return False
        return True

    def process_arguments(self, identifier, args, needs_auth=True, fallback_protocols=None):
        if fallback_protocols is None:
            fallback_protocols = list()

        packet_type = '{}_INBOUND'.format(identifier.upper())
        for protocol in [self.client.packet_handler]+fallback_protocols:
            expected_pairs = protocol[packet_type].value
            expected_argument_names = [x[0] for x in expected_pairs]
            expected_types = [x[1] for x in expected_pairs]
            if not self.validate_net_cmd(args, *expected_types, needs_auth=needs_auth):
                continue

            return dict(zip(expected_argument_names, args))
        return None

    def net_cmd_hi(self, args):
        """ Handshake.

        HI#<hdid:string>#%

        :param args: a list containing all the arguments
        """
        if not self.validate_net_cmd(args, ArgType.STR, needs_auth=False):
            return

        # Record new HDID and IPID if needed
        self.client.hdid = args[0]
        if self.client.hdid not in self.client.server.hdid_list:
            self.client.server.hdid_list[self.client.hdid] = []
        if self.client.ipid not in self.client.server.hdid_list[self.client.hdid]:
            self.client.server.hdid_list[self.client.hdid].append(self.client.ipid)
            self.client.server.dump_hdids()

        # Check if the client is banned
        for ipid in self.client.server.hdid_list[self.client.hdid]:
            if self.server.ban_manager.is_banned(ipid):
                self.client.send_ooc_others('Banned client with HDID {} and IPID {} attempted to '
                                            'join the server but was refused entrance.'
                                            .format(self.client.hdid, self.client.ipid),
                                            is_officer=True)
                self.client.send_command('BD')
                self.client.disconnect()
                return

        if self.client.hdid != 'ms2-prober' or self.server.config['show_ms2-prober']:
            logger.log_server('Connected. HDID: {}.'.format(self.client.hdid), self.client)
        self.client.send_command('ID', self.client.id, self.server.software,
                                 self.server.get_version_string())
        self.client.send_command('PN', self.server.get_player_count(),
                                 self.server.config['playerlimit'])
        self.client.can_join += 1 # One of two conditions to allow joining

    def net_cmd_id(self, args):
        """ Client version and PV

        ID#<pv:int>#<software:string>#<version:string>#%

        """

        self.client.can_join += 1  # One of two conditions to allow joining

        def check_client_version():
            if len(args) < 2:
                self.client.version = ('DRO', '1.0.0')
                return False

            self.client.version = (args[0], args[1])

            software = args[0]
            version_list = args[1].split('.')

            # Identify version number
            if len(version_list) >= 3:
                # Such versions include DRO and AO
                release = int(version_list[0])
                major = int(version_list[1])
                minor = int(version_list[2])

                if args[0] not in ['DRO', 'AO2']:
                    return False
            else:
                # Only such version recognized now is CC
                # CC has args[1] == 'CC - Update (\d+\.)*\d+'
                if args[1].startswith('CC'):
                    release = 'CC'
                    major = float(args[1].split(' ')[-1])
                    minor = 0
                else:
                    return False

            if software == 'DRO':
                self.client.packet_handler = Clients.ClientDRO1d0d0
            else:  # AO2 protocol
                if release == 2:
                    if major >= 8 and major >= 4:
                        self.client.packet_handler = Clients.ClientAO2d8d4
                    elif major >= 8:  # KFO
                        self.client.packet_handler = Clients.ClientKFO2d8
                    elif major == 7:  # AO 2.7
                        self.client.packet_handler = Clients.ClientAO2d7
                    elif major == 6:  # AO 2.6
                        self.client.packet_handler = Clients.ClientAO2d6
                    elif major == 4 and minor == 8:  # Older DRO
                        self.client.packet_handler = Clients.ClientDROLegacy
                    else:
                        return False  # Unrecognized
                elif release == 'CC':
                    if major >= 24:
                        self.client.packet_handler = Clients.ClientCC24
                    elif major >= 22:
                        self.client.packet_handler = Clients.ClientCC22
                    else:
                        return False  # Unrecognized
            # The only way to make it here is if we have not returned False
            # If that is the case, we have successfully found a version
            return True

        if not check_client_version():
            # Warn player they are using an unknown client.
            # Assume a DRO client instruction set.
            self.client.packet_handler = Clients.ClientDRO1d0d0
            self.client.bad_version = True

        self.client.send_command('FL', 'yellowtext', 'customobjections', 'flipping',
                                 'fastloading', 'noencryption', 'deskmod', 'evidence',
                                 'cccc_ic_support', 'looping_sfx', 'additive', 'effects')

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
        # Check if client is ready to actually join, and did not do weird packet shenanigans before
        if self.client.can_join != 2:
            return
        # Check if client asked for this before but did not finish processing it
        if not self.client.can_askchaa:
            return

        self.client.can_askchaa = False # Enforce the joining process happening atomically

        # Make sure there is enough room for the client
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
        if not self.validate_net_cmd(args, ArgType.INT, needs_auth=False):
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
        if not self.validate_net_cmd(args, ArgType.INT, needs_auth=False):
            return
        if len(self.server.music_pages_ao1) > args[0] >= 0:
            self.client.send_command('EM', *self.server.music_pages_ao1[args[0]])
        else:
            self.client.send_done()
            self.client.send_area_list()
            self.client.send_motd()
            self.client.can_askchaa = True # Allow rejoining if left to lobby but did not dc.

    def net_cmd_rc(self, _):
        """ Asks for the whole character list(AO2)

        AC#%

        """

        self.client.send_command('SC', *self.server.char_list)

    def net_cmd_rm(self, _):
        """ Asks for the whole music list(AO2)

        AM#%

        """
        # Force the server to rebuild the music list, so that clients who just join get the correct
        # music list (as well as every time they request an updated music list directly).

        full_music_list = self.server.build_music_list_ao2(include_areas=True,
                                                           include_music=True)
        self.client.send_command('SM', *full_music_list)

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
        self.client.can_askchaa = True # Allow rejoining if left to lobby but did not dc.

    def net_cmd_cc(self, args):
        """ Character selection.

        CC#<client_id:int>#<char_id:int>#<hdid:string>#%

        """
        if not self.validate_net_cmd(args, ArgType.INT, ArgType.INT, ArgType.STR,
                                     needs_auth=False):
            return
        cid = args[1]
        try:
            self.client.change_character(cid)
        except ClientError:
            return
        self.client.last_active = Constants.get_time()

    def net_cmd_ms(self, args):
        """ IC message.

        Refer to the implementation for details.

        """

        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc("You have been muted by a moderator.")
            return
        if self.client.area.ic_lock and not self.client.is_staff():
            self.client.send_ooc("IC chat in this area has been locked by a moderator.")
            return
        if not self.client.area.can_send_message():
            return
        pargs = self.process_arguments('ms', args)
        if not pargs:
            return

        # First, check if the player just sent the same message with the same character and did
        # not receive any other messages in the meantime.
        # This helps prevent record these messages and retransmit it to clients who may want to
        # filter these out
        if (pargs['text'] == self.client.last_ic_raw_message and self.client.last_ic_received_mine
            and self.client.get_char_name() == self.client.last_ic_char):
            return

        if not self.client.area.iniswap_allowed:
            if self.client.area.is_iniswap(self.client, pargs['pre'], pargs['anim'],
                                           pargs['folder']):
                self.client.send_ooc("Iniswap is blocked in this area.")
                return
        if pargs['folder'] in self.client.area.restricted_chars and not self.client.is_staff():
            self.client.send_ooc('Your character is restricted in this area.')
            return
        if pargs['msg_type'] not in ('chat', '0', '1'):
            return
        if pargs['anim_type'] not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
            return
        if pargs['cid'] != self.client.char_id:
            return
        if pargs['sfx_delay'] < 0:
            return
        if pargs['button'] not in (0, 1, 2, 3, 4, 5, 6, 7): # Shouts
            return
        if pargs['button'] > 0 and not self.client.area.bullet and not self.client.is_staff():
            self.client.send_ooc('Bullets are disabled in this area.')
            return
        if pargs['evidence'] < 0:
            return
        if pargs['ding'] not in (0, 1, 2, 3, 4, 5, 6, 7): # Effects
            return
        if pargs['color'] not in (0, 1, 2, 3, 4, 5, 6):
            return
        if pargs['color'] == 5 and not self.client.is_mod and not self.client.is_cm:
            pargs['color'] = 0
        if pargs['color'] == 6:
            # Remove all unicode to prevent now yellow text abuse
            pargs['text'] = re.sub(r'[^\x00-\x7F]+', ' ', pargs['text'])
            if len(pargs['text'].strip(' ')) == 1:
                pargs['color'] = 0
            else:
                if pargs['text'].strip(' ') in ('<num>', '<percent>', '<dollar>', '<and>'):
                    pargs['color'] = 0
        if self.client.pos:
            pargs['pos'] = self.client.pos
        else:
            if pargs['pos']  not in ('def', 'pro', 'hld', 'hlp', 'jud', 'wit'):
                return
        self.client.pos = pargs['pos']

        # At this point, the message is guaranteed to be sent
        # First, update last raw message sent *before* any transformations. That is so that the
        # server can accurately ignore client sending the same message over and over again
        self.client.last_ic_raw_message = pargs['text']
        self.client.last_ic_char = self.client.get_char_name()

        # Truncate and alter message if message effect is in place
        raw_msg = pargs['text'][:256]
        msg = raw_msg
        if self.client.gimp: #If you are gimped, gimp message.
            msg = Constants.gimp_message()
        if self.client.disemvowel: #If you are disemvoweled, replace string.
            msg = Constants.disemvowel_message(msg)
        if self.client.disemconsonant: #If you are disemconsonanted, replace string.
            msg = Constants.disemconsonant_message(msg)
        if self.client.remove_h: #If h is removed, replace string.
            msg = Constants.remove_h_message(msg)

        gag_replaced = False
        if self.client.is_gagged:
            allowed_starters = ('(', '*', '[')
            if msg != ' ' and not msg.startswith(allowed_starters):
                gag_replaced = True
                msg = Constants.gagged_message()
            if msg != raw_msg:
                self.client.send_ooc_others('(X) {} [{}] tried to say `{}` but is currently gagged.'
                                            .format(self.client.displayname, self.client.id,
                                                    raw_msg),
                                            is_zstaff_flex=True, in_area=True)

        # Censor passwords if login command accidentally typed in IC
        for password in self.server.all_passwords:
            for login in ['login ', 'logincm ', 'loginrp ', 'logingm ']:
                if login + password in msg:
                    msg = msg.replace(password, '[CENSORED]')

        if pargs['evidence']:
            evidence_position = self.client.evi_list[pargs['evidence']] - 1
            if self.client.area.evi_list.evidences[evidence_position].pos != 'all':
                self.client.area.evi_list.evidences[evidence_position].pos = 'all'
                self.client.area.broadcast_evidence_list()

        # If client has GlobalIC enabled, set area range target to intended range and remove
        # GlobalIC prefix if needed.
        if self.client.multi_ic is None or not msg.startswith(self.client.multi_ic_pre):
            area_range = range(self.client.area.id, self.client.area.id + 1)
        else:
            # As msg.startswith('') is True, this also accounts for having no required prefix.
            start, end = self.client.multi_ic[0].id, self.client.multi_ic[1].id + 1
            start_area = self.server.area_manager.get_area_by_id(start)
            end_area = self.server.area_manager.get_area_by_id(end-1)
            area_range = range(start, end)

            truncated_msg = msg.replace(self.client.multi_ic_pre, '', 1)
            if start != end-1:
                self.client.send_ooc('Sent global IC message "{}" to areas {} through {}.'
                                     .format(truncated_msg, start_area.name, end_area.name))
            else:
                self.client.send_ooc('Sent global IC message "{}" to area {}.'
                                     .format(truncated_msg, start_area.name))

        pargs['msg'] = msg
        pargs['evidence'] = self.client.evi_list[pargs['evidence']]
        pargs['showname'] = '' # Dummy value, actual showname is computed later

        # Compute pairs
        # Based on tsuserver3.3 code
        # Only do this if character is paired, which would only happen for AO 2.6+ clients

        # Handle AO 2.8 logic
        # AO 2.8 sends their charid_pair in slightly longer format (\d+\^\d+)
        # The first bit corresponds to the proper charid_pair, the latter one to whether
        # the character should appear in front or behind the pair. We still want to extract
        # charid_pair so pre-AO 2.8 still see the pair; but make it so that AO 2.6 can send pair
        # messages. Thus, we 'invent' the missing arguments based on available info.
        if 'charid_pair_pair_order' in pargs:
            # AO 2.8 sender
            pargs['charid_pair'] = int(pargs['charid_pair_pair_order'].split('^')[0])
        elif 'charid_pair' in pargs:
            # AO 2.6 sender
            pargs['charid_pair_pair_order'] = f'{pargs["charid_pair"]}^0'
        else:
            # E.g. DRO
            pargs['charid_pair'] = -1
            pargs['charid_pair_pair_order'] = -1

        self.client.charid_pair = pargs['charid_pair'] if 'charid_pair' in pargs else -1
        self.client.offset_pair = pargs['offset_pair'] if 'offset_pair' in pargs else 0
        self.client.flip = pargs['flip']
        self.client.char_folder = pargs['folder']

        if pargs['anim_type'] not in (5, 6):
            self.client.last_sprite = pargs['anim']

        pargs['other_offset'] = 0
        pargs['other_emote'] = 0
        pargs['other_flip'] = 0
        pargs['other_folder'] = ''
        if 'charid_pair' not in pargs or pargs['charid_pair'] < -1:
            pargs['charid_pair'] = -1
            pargs['charid_pair_pair_order'] = -1

        if pargs['charid_pair'] > -1:
            for target in self.client.area.clients:
                if target == self.client:
                    continue
                # Check pair has accepted pair
                if target.char_id != self.client.charid_pair:
                    continue
                if target.charid_pair != self.client.char_id:
                    continue
                # Check pair is in same position
                if target.pos != self.client.pos:
                    continue

                pargs['other_offset'] = target.offset_pair
                pargs['other_emote'] = target.last_sprite
                pargs['other_flip'] = target.flip
                pargs['other_folder'] = target.char_folder
                break
            else:
                # There are no clients who want to pair with this client
                pargs['charid_pair'] = -1
                pargs['offset_pair'] = 0
                pargs['charid_pair_pair_order'] = -1

        for area_id in area_range:
            target_area = self.server.area_manager.get_area_by_id(area_id)
            for c in target_area.clients:
                c.send_ic(params=pargs, sender=self.client, gag_replaced=gag_replaced)

            target_area.set_next_msg_delay(len(msg))

            # Deal with shoutlog
            if pargs['button'] > 0:
                info = 'used shout {} with the message: {}'.format(pargs['button'], msg)
                target_area.add_to_shoutlog(self.client, info)

        self.client.area.set_next_msg_delay(len(msg))
        logger.log_server('[IC][{}][{}]{}'
                          .format(self.client.area.id, self.client.get_char_name(), msg),
                          self.client)

        # Sending IC messages reveals sneaked players
        if not self.client.is_staff() and not self.client.is_visible:
            self.client.change_visibility(True)
            self.client.send_ooc_others('(X) {} [{}] revealed themselves by talking ({}).'
                                        .format(self.client.displayname, self.client.id,
                                                self.client.area.id),
                                        is_zstaff=True)

        self.server.tasker.create_task(self.client,
                                       ['as_afk_kick', self.client.area.afk_delay,
                                        self.client.area.afk_sendto])
        if self.client.area.is_recording:
            self.client.area.recorded_messages.append(args)

        self.client.last_ic_message = msg
        self.client.last_active = Constants.get_time()

    def net_cmd_ct(self, args):
        """ OOC Message

        CT#<name:string>#<message:string>#%

        """
        if self.client.is_ooc_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc("You have been muted by a moderator.")
            return
        if not self.validate_net_cmd(args, ArgType.STR, ArgType.STR, needs_auth=False):
            return
        if args[0] == '' or not self.client.is_valid_name(args[0]):
            self.client.send_ooc('You must insert a name with at least one letter.')
            return
        if args[0].startswith(' '):
            self.client.send_ooc('You must insert a name that starts with a letter.')
            return
        if Constants.contains_illegal_characters(args[0]):
            self.client.send_ooc('Your name contains an illegal character.')
            return
        if self.server.config['hostname'] in args[0] or '<dollar>G' in args[0]:
            self.client.send_ooc('That name is reserved.')
            return

        # After this the name is validated
        if self.client.name != args[0] and self.client.fake_name != args[0]:
            if self.client.is_valid_name(args[0]):
                self.client.name = args[0]
                self.client.fake_name = args[0]
            else:
                self.client.fake_name = args[0]
                self.client.name = ''
        if args[1].startswith('/'):
            spl = args[1][1:].split(' ', 1)
            cmd = spl[0]
            arg = ''
            if len(spl) == 2:
                arg = spl[1][:1024]
            try:
                called_function = 'ooc_cmd_{}'.format(cmd)
                function = None # Double assignment to check if it matched to a function later
                function = getattr(self.server.commands, called_function)
            except AttributeError:
                try:
                    function = getattr(self.server.commands_alt, called_function)
                except AttributeError:
                    logger.log_print('Attribute error with ' + called_function)
                    self.client.send_ooc('Invalid command.')

            if function:
                try:
                    function(self.client, arg)
                except TsuserverException as ex:
                    self.client.send_ooc(ex)
        else:
            # Censor passwords if accidentally said without a slash in OOC
            for password in self.server.all_passwords:
                for login in ['login ', 'logincm ', 'loginrp ', 'logingm ']:
                    if login + password in args[1]:
                        args[1] = args[1].replace(password, '[CENSORED]')
            if self.client.disemvowel: #If you are disemvoweled, replace string.
                args[1] = Constants.disemvowel_message(args[1])
            if self.client.disemconsonant: #If you are disemconsonanted, replace string.
                args[1] = Constants.disemconsonant_message(args[1])
            if self.client.remove_h: #If h is removed, replace string.
                args[1] = Constants.remove_h_message(args[1])

            self.client.area.send_command('CT', self.client.name, args[1])
            self.client.last_ooc_message = args[1]
            logger.log_server('[OOC][{}][{}][{}]{}'
                              .format(self.client.area.id, self.client.get_char_name(),
                                      self.client.name, args[1]), self.client)
        self.client.last_active = Constants.get_time()

    def net_cmd_mc(self, args):
        """ Play music.

        MC#<song_name:int>#<???:int>#%

        """
        # First attempt to switch area,
        # because music lists typically include area names for quick access
        try:
            delimiter = args[0].find('-')
            area = self.server.area_manager.get_area_by_name(args[0][delimiter+1:])
            self.client.change_area(area, from_party=True if self.client.party else False)

        # Otherwise, attempt to play music.
        except (AreaError, ValueError):
            if self.client.is_muted:  # Checks to see if the client has been muted by a mod
                self.client.send_ooc("You have been muted by a moderator.")
                return
            if not self.client.is_dj:
                self.client.send_ooc('You were blockdj\'d by a moderator.')
                return
            # We have to use fallback protocols for AO2d6 like clients, because if for whatever
            # reason if they don't set an in-client showname, they send less arguments. In
            # particular, they behave like DRO.
            pargs = self.process_arguments('MC', args, fallback_protocols=[Clients.ClientDROLegacy])
            if not pargs:
                return

            if 'cid' not in pargs or int(pargs['cid']) != self.client.char_id:
                return
            if self.client.change_music_cd():
                self.client.send_ooc('You changed song too many times recently. Please try again '
                                     'after {} seconds.'.format(int(self.client.change_music_cd())))
                return

            try:
                self.client.area.play_track(pargs['name'], self.client, raise_if_not_found=True,
                                            reveal_sneaked=True, pargs=pargs)
            except ServerError.MusicNotFoundError:
                self.client.send_ooc('Unrecognized area or music `{}`.'.format(args[0]))
            except ServerError:
                return
        except (ClientError, PartyError) as ex:
            self.client.send_ooc(ex)

        self.client.last_active = Constants.get_time()

    def net_cmd_rt(self, args):
        """ Plays the Testimony/CE animation.

        RT#<type:string>#%

        """
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc('You have been muted by a moderator.')
            return
        if not self.validate_net_cmd(args, ArgType.STR):
            return
        if args[0] not in ('testimony1', 'testimony2', 'testimony3', 'testimony4'):
            return
        self.client.area.send_command('RT', args[0])
        self.client.area.add_to_judgelog(self.client, 'used judge button {}.'.format(args[0]))
        logger.log_server('[{}]{} used judge button {}.'
                          .format(self.client.area.id, self.client.get_char_name(), args[0]),
                          self.client)
        self.client.last_active = Constants.get_time()

    def net_cmd_hp(self, args):
        """ Sets the penalty bar.

        HP#<type:int>#<new_value:int>#%

        """
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc("You have been muted by a moderator")
            return
        if not self.validate_net_cmd(args, ArgType.INT, ArgType.INT):
            return
        try:
            self.client.area.change_hp(args[0], args[1])
            info = 'changed penalty bar {} to {}.'.format(args[0], args[1])
            self.client.area.add_to_judgelog(self.client, info)
            logger.log_server('[{}]{} changed HP ({}) to {}'
                              .format(self.client.area.id, self.client.get_char_name(),
                                      args[0], args[1]), self.client)
        except AreaError:
            return
        self.client.last_active = Constants.get_time()

    def net_cmd_pe(self, args):
        """ Adds a piece of evidence.

        PE#<name: string>#<description: string>#<image: string>#%

        """
        if len(args) < 3:
            return
#        evi = Evidence(args[0], args[1], args[2], self.client.pos)
        self.client.area.evi_list.add_evidence(self.client, args[0], args[1], args[2], 'all')
        self.client.area.broadcast_evidence_list()
        self.client.last_active = Constants.get_time()

    def net_cmd_de(self, args):
        """ Deletes a piece of evidence.

        DE#<id: int>#%

        """

        self.client.area.evi_list.del_evidence(self.client, self.client.evi_list[int(args[0])])
        self.client.area.broadcast_evidence_list()
        self.client.last_active = Constants.get_time()

    def net_cmd_ee(self, args):
        """ Edits a piece of evidence.

        EE#<id: int>#<name: string>#<description: string>#<image: string>#%

        """

        if len(args) < 4:
            return

        evi = (args[1], args[2], args[3], 'all')

        self.client.area.evi_list.edit_evidence(self.client, self.client.evi_list[int(args[0])], evi)
        self.client.area.broadcast_evidence_list()
        self.client.last_active = Constants.get_time()

    def net_cmd_zz(self, _):
        """ Sent on mod call.

        """
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc('You have been muted by a moderator.')
            return

        if not self.client.can_call_mod():
            self.client.send_ooc('You must wait 30 seconds between mod calls.')
            return

        current_time = strftime("%H:%M", localtime())
        message = ('[{}] {} ({}) called for a moderator in {} ({}).'
                   .format(current_time, self.client.get_char_name(), self.client.get_ip(),
                           self.client.area.name, self.client.area.id))

        self.server.send_all_cmd_pred('ZZ', message, pred=lambda c: c.is_mod or c.is_cm)
        self.client.set_mod_call_delay()
        logger.log_server('[{}][{}]{} called a moderator.'
                          .format(self.client.get_ip(), self.client.area.id,
                                  self.client.get_char_name()))

    def net_cmd_re(self, args):
        # Unsupported
        raise KeyError('Client using {} {} sent an unsupported RE packet.'
                       .format(self.client.version[0], self.client.version[1]))

    def net_cmd_pw(self, args):
        # Ignore packet
        # For now, TsuserverDR will not implement a character password system
        # However, so that it stops raising errors for clients, an empty method is implemented
        # Well, not empty, there are these comments which makes it not empty
        # but not code is run.
        pass

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
        'RE': net_cmd_re,  # ??? (Unsupported)
        'PW': net_cmd_pw,  # character password (only on CC/KFO clients)
        'opKICK': net_cmd_opKICK,  # /kick with guard on
        'opBAN': net_cmd_opBAN,  # /ban with guard on
    }
