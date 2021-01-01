# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-21 Chrezm/Iuvee <thechrezm@gmail.com>
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
import random
import unittest

from typing import List, Set

from unittest.mock import Mock

from server.aoprotocol import AOProtocol
from server.area_manager import AreaManager
from server.client_manager import ClientManager
from server.exceptions import TsuserverException
from server.tasker import Tasker
from server.tsuserver import TsuserverDR

class _Unittest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if cls.__name__[0] == '_':
            cls.skipTest('', reason='')
        print('\nTesting {}: '.format(cls.__name__), end=' ')
        cls.server = _TestTsuserverDR()
        cls.clients: List[_TestClientManager._Testclient] = cls.server.client_list
        cls.area0: AreaManager.Area  = cls.server.area_manager.get_area_by_id(0)
        cls.area1: AreaManager.Area = cls.server.area_manager.get_area_by_id(1)
        cls.area2: AreaManager.Area = cls.server.area_manager.get_area_by_id(2)
        cls.area3: AreaManager.Area = cls.server.area_manager.get_area_by_id(3)
        cls.area4: AreaManager.Area = cls.server.area_manager.get_area_by_id(4)
        cls.area5: AreaManager.Area = cls.server.area_manager.get_area_by_id(5)
        cls.area6: AreaManager.Area = cls.server.area_manager.get_area_by_id(6)
        cls.area7: AreaManager.Area = cls.server.area_manager.get_area_by_id(7)

        cls.a0_name: str = cls.area0.name
        cls.a1_name: str = cls.area1.name
        cls.a2_name: str = cls.area2.name
        cls.a2_name_s: str = cls.a2_name.replace(', ', ',\ ') # comma in Class Trial Room, 2
        cls.a3_name: str = cls.area3.name
        cls.a4_name: str = cls.area4.name
        cls.a5_name: str = cls.area5.name
        cls.a6_name: str = cls.area6.name
        cls.a7_name: str = cls.area7.name

    @classmethod
    def setUpClients(cls, num_clients):
        cls.server.make_clients(num_clients)

        cls.c0: _TestClientManager._TestClient = cls.clients[0]
        cls.c0_cname: str = cls.c0.get_char_name() #'Kaede Akamatsu_HD'
        cls.c0_dname: str = cls.c0.displayname
        if num_clients == 1: return

        cls.c1: _TestClientManager._TestClient = cls.clients[1]
        cls.c1_cname: str = cls.c1.get_char_name() #'Shuichi Saihara_HD'
        cls.c1_dname: str = cls.c1.displayname
        if num_clients == 2: return

        cls.c2: _TestClientManager._TestClient = cls.clients[2]
        cls.c2.showname = 'showname2'
        cls.c2_cname: str = cls.c2.get_char_name() #'Maki Harukawa_HD'
        cls.c2_dname: str = cls.c2.displayname
        if num_clients == 3: return

        cls.c3: _TestClientManager._TestClient = cls.clients[3]
        cls.c3.showname = 'showname3'
        cls.c3_cname: str = cls.c3.get_char_name() #'Monokuma_HD'
        cls.c3_dname: str = cls.c3.displayname
        if num_clients == 4: return

        cls.c4: _TestClientManager._TestClient = cls.clients[4]
        cls.c4.showname = 'showname4'
        cls.c4_cname: str = cls.c4.get_char_name() #'SPECTATOR'
        cls.c4_dname: str = cls.c4.displayname
        if num_clients == 5: return

        cls.c5: _TestClientManager._TestClient = cls.clients[5]
        cls.c5_cname: str = cls.c5.get_char_name() #'SPECTATOR'
        cls.c5_dname: str = cls.c5.displayname

    def list2reason(self, exc_list):
        if exc_list and exc_list[-1][0] is self:
            return exc_list[-1][1]

    def assert_property(self, yes, no, group, pred):
        if yes == 0:
            yes = set()
        if no == 0:
            no = set()

        if group == 'C':
            structure = self.server.client_manager.clients
        elif group == 'A':
            structure = self.server.area_manager.areas

        if yes == 1:
            yes = {x for x in structure if x not in no}
        if no == 1:
            no = {x for x in structure if x not in yes}

        for x in yes:
            self.assertTrue(pred(x), x)
        for x in no:
            self.assertFalse(pred(x), x)

    def tearDown(self):
        """
        Check if any packets were unaccounted for. Only do so if test passed.
        """

        # Test checker by hynekcer (2016): https://stackoverflow.com/a/39606065

        result = self.defaultTestResult()  # these 2 methods have no side effects
        self._feedErrorsToResult(result, self._outcome.errors)
        error = self.list2reason(result.errors)
        failure = self.list2reason(result.failures)

        if error or failure:
            return

        for c in self.clients:
            if c:
                c.assert_no_packets()
                c.assert_no_ooc()
                c.assert_no_ic()

    @classmethod
    def tearDownClass(cls):
        for (logger, handler) in cls.server.logger_handlers:
            handler.close()
            logger.removeHandler(handler)
        cls.server.disconnect_all()

class _TestSituation3(_Unittest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        super().setUpClients(3)

class _TestSituation4(_Unittest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        super().setUpClients(4)

class _TestSituation5(_Unittest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        super().setUpClients(5)

class _TestSituation6(_Unittest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        super().setUpClients(6)

class _TestSituation4Mc12(_TestSituation4):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c1.make_mod()
        cls.c2.make_mod()

class _TestSituation4Mc1Gc2(_TestSituation4):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c1.make_mod()
        cls.c2.make_gm()

class _TestSituation5Mc1Gc2(_TestSituation5):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c1.make_mod()
        cls.c2.make_gm()

class _TestSituation6Mc1Gc25(_TestSituation6):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c1.make_mod()
        cls.c2.make_gm()
        cls.c5.make_gm()

class _TestClientManager(ClientManager):
    class _TestClient(ClientManager.Client):
        def __init__(self, *args, my_protocol=None):
            """ Overwrites client_manager.ClientManager.Client.__init__ """

            super().__init__(*args)

            if my_protocol is None:
                my_protocol = self.server.ao_protocol()
            self.my_protocol = my_protocol
            self.received_packets = list()
            self.received_ooc = list()
            self.received_ic = list()

        def disconnect(self, assert_no_outstanding=False):
            """ Overwrites client_manager.ClientManager.Client.disconnect """

            self.my_protocol.connection_lost(None, client=self)

            if assert_no_outstanding:
                self.assert_no_packets()
                self.assert_no_ooc()
            if self.id >= 0:
                self.server.client_list[self.id] = None

        def send_command(self, command, *args):
            """ Overwrites ClientManager.Client.send_command """

            self.send_command_stc(command, *args)

        def send_command_stc(self, command_type, *args):
            if len(args) > 1 and isinstance(args[1], TsuserverException):
                new_args = [args[0], args[1].message]
                args = tuple(new_args)
            self.received_packets.append([command_type, args])
            self.receive_command_stc(command_type, *args)

        def send_command_cts(self, buffer):
            self.my_protocol.data_received(buffer.encode('utf-8'))

        def ooc(self, message, username=None):
            if username is None:
                username = self.name

            user = self.convert_symbol_to_word(username)
            message = self.convert_symbol_to_word(message)
            buffer = "CT#{}#{}#%".format(user, message)
            self.send_command_cts(buffer)

        @staticmethod
        def convert_symbol_to_word(mes):
            if mes is None:
                return None
            mes = mes.replace('#', '<num>')
            mes = mes.replace('$', '<dollar>')
            return mes

        @staticmethod
        def convert_word_to_symbol(mes):
            if mes is None:
                return None
            mes = mes.replace('<num>', '#')
            mes = mes.replace('<dollar>', '$')
            return mes

        def make_mod(self, over=True):
            if self.is_mod:
                return
            self.ooc('/login {}'.format(self.server.config['modpass']))
            self.assert_packet('FM', None)
            self.assert_ooc('Logged in as a moderator.', over=over)
            # Look for all officers and assert messages of this client's login
            for c in self.server.client_manager.clients:
                if (c.is_mod or c.is_cm) and c != self:
                    c.assert_ooc('{} [{}] logged in as a moderator.'
                                 .format(self.name, self.id), over=True)
            assert self.is_mod

        def make_cm(self, over=True):
            if self.is_cm:
                return
            self.ooc('/logincm {}'.format(self.server.config['cmpass']))
            self.assert_packet('FM', None)
            self.assert_ooc('Logged in as a community manager.', over=over)
            # Look for all officers and assert messages of this client's login
            for c in self.server.client_manager.clients:
                if (c.is_mod or c.is_cm) and c != self:
                    c.assert_ooc('{} [{}] logged in as a community manager.'
                                 .format(self.name, self.id), over=True)
            assert self.is_cm

        def make_gm(self, over=True):
            if self.is_gm:
                return
            self.ooc('/loginrp {}'.format(self.server.config['gmpass']))
            self.assert_packet('FM', None)
            self.assert_ooc('Logged in as a game master.', over=over)
            # Look for all officers and assert messages of this client's login
            for c in self.server.client_manager.clients:
                if (c.is_mod or c.is_cm) and c != self:
                    c.assert_ooc('{} [{}] logged in as a game master with the global password.'
                                 .format(self.name, self.id), over=True)
            assert self.is_gm

        def make_normie(self, over=True, other_over=lambda c: True):
            if not self.is_staff():
                return
            # Find rank before logging out to assert their logout message to other officers
            if self.is_gm:
                role = 'game master'
            elif self.is_cm:
                role = 'community manager'
            elif self.is_mod:
                role = 'moderator'
            self.ooc('/logout')
            self.assert_ooc('You are no longer logged in.', ooc_over=over)
            self.assert_packet('FM', None, over=over)

            # Assert command for any officers of this client's logout
            for c in self.server.client_manager.clients:
                if (c.is_mod or c.is_cm) and c != self:
                    c.assert_ooc('{} [{}] is no longer a {}.'.format(self.name, self.id, role),
                                 over=other_over(c))
            assert not self.is_staff()

        def move_area(self, area_id, discard_packets=True, discard_trivial=False):
            as_command = random.randint(0, 1)
            area = self.server.area_manager.get_area_by_id(area_id)
            if as_command:
                self.ooc('/area {}'.format(area_id))
            else:
                name = area.name
                buffer = 'MC#{}-{}#{}#%'.format(area_id, name, self.char_id)
                self.send_command_cts(buffer)

            assert self.area.id == area_id, (self.area.id, area_id, as_command)

            if discard_trivial:
                # Discard the trivial packets
                # Note we use somewhere because MS usually comes between LE and FM
                packets_to_discard = (
                                    ['HP', None],
                                    ['HP', None],
                                    ['BN', None],
                                    ['LE', None],
                                    ['FM', None],
                                    ['BN', None],
                                    )
                for packet in packets_to_discard:
                    self.discard_packet(packet, somewhere=True)

                # Discard IC blankpost and OOC standard notification
                _, x = self.search_match(['MS', None],
                                          self.received_packets, somewhere=True, remove_match=True,
                                          allow_partial_match=True)
                self.discard_ic(x[1])

                _, x = self.search_match(['CT', ('<dollar>H', 'Changed area to')],
                                          self.received_packets, somewhere=True, remove_match=True,
                                          allow_partial_match=True)
                self.discard_ooc(x[1])

            elif discard_packets:
                self.discard_all()

        def check_match(self, exp_args, act_args, allow_partial_match=False):
            assert len(exp_args) == len(act_args), (len(exp_args), len(act_args))

            for exp_arg, act_arg in zip(exp_args, act_args):
                if exp_arg is None:
                    continue
                if isinstance(exp_arg, tuple):
                    assert len(exp_arg) == len(act_arg)

                    for i, param in enumerate(exp_arg):
                        if param is None:
                            continue
                        if allow_partial_match:
                            condition = act_arg[i].startswith(param)
                        else:
                            condition = param == act_arg[i]
                        assert condition, (i, param, act_arg[i])
                elif isinstance(act_arg, tuple):
                    assert exp_arg == act_arg[0], (exp_arg, act_arg[0])
                elif isinstance(exp_arg, str) and isinstance(act_arg, str) and allow_partial_match:
                    assert act_arg.startswith(exp_arg)
                else:
                    assert exp_arg == act_arg, (exp_arg, act_arg)

        def search_match(self, exp_args, structure, somewhere=False, remove_match=True,
                         allow_partial_match=False):
            if not somewhere:
                to_look = structure[:1]
            else:
                to_look = structure

            for i, act_args in enumerate(to_look):
                try:
                    self.check_match(exp_args, act_args, allow_partial_match=allow_partial_match)
                except AssertionError:
                    continue
                else:
                    if remove_match:
                        structure.pop(i)
                    return i, act_args
            else:
                if somewhere:
                    connector = 'somewhere among'
                else:
                    connector = 'at the start of'
                err = 'Cannot find \r\n {} \r\n{} the packets of {}'.format(exp_args, connector, self)
                err += ('\r\nCurrent packets: \r\n*{}'
                        .format('\r\n*'.join([str(x) for x in structure])))
                raise AssertionError(err)

        def assert_packet(self, command_type, args, over=False, ooc_over=False, ic_over=False,
                          somewhere=False, allow_partial_match=False):
            """
            Assert that the client does not have a particular packet among its unaccounted ones.

            Parameters
            ----------
            command_type: str
                Packet type
            args: list pf str
                Packet arguments
            somewhere: boolean, optional
                If True, will assert that the client has not a particular packet among any of its
                unaccounted ones. If False, will assert that the client has not as its earliest
                unaccounted packet the given packet.
            """

            err = '{} expected packets, found none'.format(self)
            assert len(self.received_packets) > 0, err
            self.search_match([command_type, args], self.received_packets, somewhere=somewhere,
                              allow_partial_match=allow_partial_match)

            if over:
                err = ('{} expected no more packets (did you accidentally put over=True?)'
                       .format(self))
                err += ('\r\nCurrent packets: \r\n*{}'
                        .format('\r\n*'.join([str(x) for x in self.received_packets])))
                assert len(self.received_packets) == 0, err
            elif ooc_over or ic_over:
                # Assumes actual over checks are done manually
                pass
            else:
                err = ('{} expected more packets (did you forget to put over=True?)'
                       .format(self))
                assert len(self.received_packets) != 0, err

        def assert_no_packets(self):
            """
            Assert that the client has no packets that have not been accounted for.

            Raises
            ------
            AssertionError:
                If the client has some outstanding packets.
            """

            err = ('{} expected no outstanding packets, found {}.'
                   .format(self, self.received_packets))
            assert len(self.received_packets) == 0, err

        def assert_not_packet(self, command_type, args, somewhere=True):
            """
            Assert that the client does not have a particular packet among its unaccounted ones.

            Parameters
            ----------
            command_type: str
                Packet type
            args: list pf str
                Packet arguments
            somewhere: boolean, optional
                If True, will assert that the client has not a particular packet among any of its
                unaccounted ones. If False, will assert that the client has not as its earliest
                unaccounted packet the given packet.
            """

            try:
                self.search_match([command_type, args], self.received_packets,
                                  somewhere=somewhere, remove_match=False)
            except AssertionError:
                pass
            else:
                raise AssertionError('Found packet {} {} when expecting not to find it.'
                                     .format(command_type, args))

        def assert_ooc(self, message, username=None, over=False, ooc_over=False,
                       check_CT_packet=True, somewhere=False, allow_partial_match=False):
            """
            Assert that the client has a particular message as an unaccounted OOC message.

            Parameters
            ----------
            message: str
                Message to test.
            username: str, optional
                Username of the earliest expected OOC message. If None, it will assume the server's
                hostname.
            over: boolean, optional
                If True, it will assume the client has no further packets to account for, even
                those that are not from OOC messages. If False, it will assume the client still
                has some packets to account for.
            ooc_over: boolean, optional
                If True, it will assume the client has no further OOC packets to account for, but
                still possibly some other non-OOC packets. If False, it will assume the client
                still has some packets to account for.
            check_CT_packet: boolean, optional
                If True, it will also try and account that the earliest unaccounted packet is an
                OOC packet. If False, it will not do so.
            somewhere: boolean, optional
                If True, it will try and account for an unaccounted OOC message anywhere among the
                client's unaccounted packets. If False, it will only look at the earliest
                unaccounted message.
            allow_partial_match: boolean, optional
                If True, instead of matching the whole message, the function will just check if the
                target unaccounted message starts with the value of message. If False, it will
                match the target unaccounted message with the value of message exactly.

            Raises
            ------
            AssertionError
                If it is unable to match the expected OOC message according to the given conditions.
            """

            if username is None:
                username = self.server.config['hostname']

            user = self.convert_symbol_to_word(username)
            message = self.convert_symbol_to_word(message)

            if check_CT_packet:
                self.assert_packet('CT', (user, message), over=over, ooc_over=ooc_over,
                                   somewhere=somewhere, allow_partial_match=allow_partial_match)

            err = 'Expected OOC messages, found none.'
            assert len(self.received_ooc) > 0, err

            self.search_match([user, message], self.received_ooc, somewhere=somewhere,
                              allow_partial_match=allow_partial_match)

            if over or ooc_over:
                err = 'Unhandled OOC messages for {}'.format(self)
                err += ('\r\nCurrent OOC: {}'
                        .format('\r\n*'.join([str(x) for x in self.received_ooc])))
                assert len(self.received_ooc) == 0, err
            else:
                err = ('Expected more OOC messages, found none (did you forget to put over=True '
                       'or ooc_over=True?).')
                assert len(self.received_ooc) != 0, err

        def assert_no_ooc(self):
            """
            Assert that the client has no unaccounted OOC messages.

            Raises
            ------
            AssertionError:
                If the client has unaccounted OOC messages.
            """

            err = ('{} expected no more OOC messages, found {}'
                   .format(self, self.received_ooc))
            assert len(self.received_ooc) == 0, err

        def assert_not_ooc(self, message, username=None, somewhere=True):
            """
            Assert that the client does not have a particular OOC message among its unaccounted
            OOC messages.

            Parameters
            ----------
            message: str
                Message to test.
            username: str, optional
                Username of the earliest expected OOC message. If None, it will assume the server's
                hostname.
            somewhere: boolean, optional
                If True, it will try and account for an unaccounted OOC message anywhere among the
                client's unaccounted packets. If False, it will only look at the earliest
                unaccounted message.

            Raises
            ------
            AssertionError:
                If the client has an OOC message matching the parameters.
            """

            if username is None:
                username = self.server.config['hostname']

            user = self.convert_symbol_to_word(username)
            message = self.convert_symbol_to_word(message)

            self.assert_not_packet('CT', (user, message), somewhere=somewhere)

        def sic(self, message, msg_type=0, pre='-', folder=None, anim=None, pos=None, sfx=0,
                anim_type=0, char_id=None, sfx_delay=0, button=0, evi=None, flip=0, ding=0, color=0,
                ignore_timelimit=True):
            if folder is None:
                folder = self.get_char_name()
            if anim is None:
                anim = 'happy'
            if pos is None:
                pos = self.pos if self.pos else 'def'
            if char_id is None:
                char_id = self.char_id
            if evi is None:
                evi = 0

            # 0 = msg_type
            # 1 = pre
            # 2 = folder
            # 3 = anim
            # 4 = msg
            # 5 = pos
            # 6 = sfx
            # 7 = anim_type
            # 8 = char_id
            # 9 = sfx_delay
            # 10 = button
            # 11 = self.client.evi_list[evidence]
            # 12 = flip
            # 13 = ding
            # 14 = color

            buffer = ('MS#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#%'
                      .format(msg_type, pre, folder, anim, message, pos, sfx, anim_type, char_id,
                              sfx_delay, button, evi, flip, ding, color))
            if ignore_timelimit: # Time wasted here = 4 hours 8/10/19
                self.area.can_send_message = lambda: True
            self.send_command_cts(buffer)

        def assert_ic(self, message, over=False, ic_over=False, check_MS_packet=True,
                      allow_partial_match=False, **kwargs):
            if check_MS_packet:
                self.assert_packet('MS', None, over=over, allow_partial_match=allow_partial_match,
                                   ic_over=ic_over)

            err = 'Expected IC messages, found none.'
            assert len(self.received_ic) > 0, err

            params = self.received_ic.pop(0)
            message = self.convert_word_to_symbol(message)
            param_ids = {'msg_type': 0,
                         'pre': 1,
                         'folder': 2,
                         'anim': 3,
                         'msg': 4,
                         'pos': 5,
                         'sfx': 6,
                         'anim_type': 7,
                         'char_id': 8,
                         'sfx_delay': 9,
                         'button': 10,
                         'evi': 11,
                         'flip': 12,
                         'ding': 13,
                         'color': 14,
                         'showname': 15}

            if 'msg' not in kwargs:
                kwargs['msg'] = message

            for (item, val) in kwargs.items():
                expected = val
                got = params[param_ids[item]]
                if allow_partial_match and isinstance(got, str):
                    err = ('Wrong IC parameter {} for {}\nExpected that it began with "{}"\n'
                           'Got "{}"'.format(item, self, expected, got))
                    assert got.startswith(expected), err
                else:
                    err = ('Wrong IC parameter {} for {}\nExpected "{}"\nGot "{}"'
                           .format(item, self, expected, got))
                    assert expected == got, err

            if over or ic_over:
                assert(len(self.received_ic) == 0)
                self.discarded_ic_somewhere = False
            else:
                assert(len(self.received_ic) != 0)

        def assert_no_ic(self):
            err = ('{} expected no more IC messages, found {}'
                   .format(self, self.received_ic))
            assert len(self.received_ic) == 0, err

        def discard_packet(self, packet, somewhere=True):
            try:
                self.search_match(packet, self.received_packets, somewhere=somewhere,
                                  remove_match=True)
            except AssertionError:
                pass

        def discard_ic(self, message):
            try:
                self.search_match(message, self.received_ic, somewhere=True, remove_match=True)
            except AssertionError:
                pass

        def discard_ooc(self, message):
            try:
                self.search_match(message, self.received_ooc, somewhere=True, remove_match=True)
            except AssertionError:
                pass

        def discard_all(self):
            self.received_packets = list()
            self.received_ooc = list()
            self.received_ic = list()

        def receive_command_stc(self, command_type, *args):
            buffer = ''
            if command_type == 'decryptor': # Hi
                buffer = 'HI#FAKEHDID#%'
            elif command_type == 'ID': # Server ID
                buffer = "ID#DRO#1.0.0#%"
                assert(args[0] == self.id)
            elif command_type == 'FL': # AO 2.2.5 configs
                pass
            elif command_type == 'PN': # Player count
                pass
            elif command_type == 'SI': # Counts for char/evi/music
                pass
            elif command_type == 'SC': # Character list
                pass
            elif command_type == 'SM': # First timer music/area list
                pass
            elif command_type == 'CharsCheck': # Available characters
                pass
            elif command_type == 'HP': # Def/pro bar
                pass
            elif command_type == 'BN': # Background file
                pass
            elif command_type == 'LE': # Evidence list
                pass
            elif command_type == 'MM': # ?????????????
                pass
            elif command_type == 'OPPASS': # Guard pass
                pass
            elif command_type == 'DONE': # Done setting up courtroom
                pass
            elif command_type == 'CT': # OOC message
                self.received_ooc.append((args[0], args[1]))
            elif command_type == 'FM': # Updated music/area list
                pass
            elif command_type == 'PV': # Current character
                pass
            elif command_type == 'MS': # IC message
                # 0 = msg_type
                # 1 = pre
                # 2 = folder
                # 3 = anim
                # 4 = msg
                # 5 = pos
                # 6 = sfx
                # 7 = anim_type
                # 8 = char_id
                # 9 = sfx_delay
                # 10 = button
                # 11 = self.client.evi_list[evidence]
                # 12 = flip
                # 13 = ding
                # 14 = color
                # 15 = showname
                if not (len(args) == 16):
                    raise ValueError('Malformed MS packet for an IC message {}'.format(args))
                self.received_ic.append(args)
            elif command_type == 'MC': # Start playing track
                pass
            elif command_type == 'ZZ': # Mod call
                pass
            elif command_type == 'GM': # Gamemode switch
                pass
            elif command_type == 'TOD': # Time of day switch
                pass
            else:
                raise KeyError('Unrecognized STC argument `{}` {}'.format(command_type, args))

            if buffer:
                self.send_command_cts(buffer)

    def __init__(self, server):
        """ Overwrites client_manager.ClientManager.__init__ """

        super().__init__(server, client_obj=self._TestClient)

    def new_client(self, transport, ip=None, my_protocol=None):
        """ Overwrites client_manager.ClientManager.new_client """

        if ip is None:
            ip = "127.0.0.1"
        c = super().new_client(transport, client_obj=self._TestClient, ip=ip,
                               my_protocol=my_protocol)
        return c

class _TestAOProtocol(AOProtocol):
    def connection_lost(self, exc, client=None):
        """ Overwrites AOProtocol.connection_lost

        Is needed in the off chance the client is disconnected before the handshake is over.
        In particular, if the client is disconnected because they attempt to join a full server.
        """

        if not self.client:
            self.client = client
        if not self.ping_timeout:
            self.ping_timeout = Mock()

        super().connection_lost(exc)

class _TestTsuserverDR(TsuserverDR):
    def __init__(self):
        """ Overwrites tsuserver.TsuserverDR.__init__ """
        self.loop = asyncio.get_event_loop()

        super().__init__(client_manager=_TestClientManager, in_test=True)
        self.ao_protocol = _TestAOProtocol
        self.client_list = [None] * self.config['playerlimit']

        self.tasker = Tasker(self, self.loop)

    def create_client(self):
        new_ao_protocol = self.ao_protocol(self)
        new_ao_protocol.connection_made(None, my_protocol=new_ao_protocol)
        return new_ao_protocol.client

    def make_client(self, char_id, hdid='FAKEHDID'):
        c = self.create_client()
        c.send_command_cts("askchaa#%")
        c.send_command_cts("RC#%")
        c.send_command_cts("RM#%")
        c.send_command_cts("RD#%")

        c.send_command_cts("CC#{}#{}#{}#%".format(c.id, char_id, hdid))
        exp = self.char_list[char_id] if char_id >= 0 else self.config['spectator_name']
        res = c.get_char_name()
        assert exp == res, (char_id, exp, res)
        c.discard_all()

        return c

    def make_clients(self, number, hdid_list=None, user_list=None) -> Set[_TestClientManager._TestClient]:
        if hdid_list is None:
            hdid_list = ['FAKEHDID'] * number
        else:
            assert len(hdid_list) == number

        if user_list is None:
            user_list = ['user{}'.format(i) for i in range(number)]
        else:
            assert len(user_list) == number

        for i in range(number):
            area = self.area_manager.default_area()
            for j in range(len(self.char_list)):
                if area.is_char_available(j):
                    char_id = j
                    break
            else:
                char_id = -1

            client = self.make_client(char_id, hdid=hdid_list[i])
            client.name = user_list[i]

            for j, existing_client in enumerate(self.client_list):
                if existing_client is None:
                    self.client_list[j] = client
                    break
            else:
                j = -1
            assert j == client.id, (j, client.id)

    def disconnect_client(self, client_id, assert_no_outstanding=False):
        client = self.client_list[client_id]
        if not client:
            raise KeyError(client_id)

        client.disconnect(assert_no_outstanding=assert_no_outstanding)

    def disconnect_all(self, assert_no_outstanding=False):
        for (i, client) in enumerate(self.client_list):
            if client:
                client.disconnect()
                if assert_no_outstanding:
                    client.assert_no_packets()
                    client.assert_no_ooc()
                self.client_list[i] = None
