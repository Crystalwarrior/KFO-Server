import random
import unittest

from server.aoprotocol import AOProtocol
from server.client_manager import ClientManager
from server.exceptions import TsuserverException
from server.tsuserver import TsuserverDR

class _Unittest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print('\nTesting {}: '.format(cls.__name__), end=' ')
        if cls.__name__[0] == '_':
            cls.skipTest('', reason='')
        cls.server = _TestTsuserverDR()
        cls.clients = cls.server.client_list

    def tearDown(self):
        """
        Check if any packets were unaccounted for.
        """

        for c in self.clients:
            if c:
                c.assert_no_packets()
                c.assert_no_ooc()

    @classmethod
    def tearDownClass(cls):
        cls.server.disconnect_all()

class _TestSituation3(_Unittest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server.make_clients(3)
        cls.c0 = cls.clients[0]
        cls.c1 = cls.clients[1]
        cls.c2 = cls.clients[2]

class _TestSituation4(_Unittest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server.make_clients(4)
        cls.c0 = cls.clients[0]
        cls.c1 = cls.clients[1]
        cls.c2 = cls.clients[2]
        cls.c3 = cls.clients[3]

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

class _TestClientManager(ClientManager):
    class _TestClient(ClientManager.Client):
        def __init__(self, *args, my_protocol=None):
            super().__init__(*args)
            self.received_commands = list()
            self.received_ooc = list()
            self.my_protocol = my_protocol

        def disconnect(self):
            self.my_protocol.connection_lost(None, client=self)

        def send_command(self, command_type, *args):
            self.send_command_stc(command_type, *args)

        def send_command_stc(self, command_type, *args):
            if len(args) > 1 and isinstance(args[1], TsuserverException):
                new_args = [args[0], args[1].message]
                args = tuple(new_args)
            self.received_commands.append([command_type, args])
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

        def make_mod(self):
            if self.is_mod:
                return
            self.ooc('/login {}'.format(self.server.config['modpass']))
            self.assert_received_packet('FM', None)
            self.assert_received_ooc('Logged in as a moderator.', over=True)
            assert self.is_mod

        def make_cm(self):
            if self.is_cm:
                return
            self.ooc('/logincm {}'.format(self.server.config['cmpass']))
            self.assert_received_packet('FM', None)
            self.assert_received_ooc('Logged in as a community manager.', over=True)
            assert self.is_cm

        def make_gm(self):
            if self.is_gm:
                return
            self.ooc('/loginrp {}'.format(self.server.config['gmpass']))
            self.assert_received_packet('FM', None)
            self.assert_received_ooc('Logged in as a game master.', over=True)
            assert self.is_gm

        def make_normie(self):
            self.ooc('/logout')
            self.assert_received_ooc('You are no longer logged in.', ooc_over=True)
            self.assert_received_packet('FM', None, over=True)
            assert not (self.is_mod and self.is_cm and self.is_gm)

        def move_area(self, area_id, discard_packets=True):
            as_command = random.randint(0, 1)
            area = self.server.area_manager.get_area_by_id(area_id)
            if as_command:
                self.ooc('/area {}'.format(area_id))
            else:
                name = area.name
                buffer = 'MC#{}-{}#0#%'.format(area_id, name)
                self.send_command_cts(buffer)
            assert self.area.id == area_id, (self.area.id, area_id, as_command)

            if discard_packets:
                self.discard_all()

        def assert_no_packets(self):
            err = ('{} expected no outstanding packets, found {}.'
                   .format(self, self.received_commands))
            assert len(self.received_commands) == 0, err

        def assert_received_packet(self, command_type, args, over=False):
            assert(len(self.received_commands) > 0)
            exp_command_type, exp_args = self.received_commands.pop(0)
            assert command_type == exp_command_type, (command_type, exp_command_type)
            if isinstance(args, tuple):
                assert(len(args) == len(exp_args))
                for i, arg in enumerate(args):
                    if arg is None:
                        continue
                    assert arg == exp_args[i], (command_type, i, arg, exp_args[i])

            if over:
                err = ('{} expected no more packets (did you accidentally put over=True?)'
                       .format(self))
                assert(len(self.received_commands) == 0), err
            else:
                err = ('{} expected more packets (did you forget to put over=True?)'
                       .format(self))
                assert len(self.received_commands) != 0, err

        def assert_no_ooc(self):
            err = ('{} expected no more OOC messages, found {}'
                   .format(self, self.received_ooc))
            assert len(self.received_ooc) == 0, err

        def assert_received_ooc(self, message, username=None, over=False, ooc_over=False,
                                check_CT_packet=True):
            if username is None:
                username = self.server.config['hostname']

            user = self.convert_symbol_to_word(username)
            message = self.convert_symbol_to_word(message)
            buffer = "CT#{}#{}#%".format(user, message)
            if check_CT_packet:
                self.assert_received_packet('CT', buffer, over=over)

            assert(len(self.received_ooc) > 0)
            act_username, act_message = self.received_ooc.pop(0)
            if username is not None:
                err = ('Wrong OOC message sender. Expected "{}", got "{}".'
                       .format(username, act_username))
                assert username == act_username, err
            if message is not None:
                err = 'Wrong OOC message. Expected "{}", got "{}".'.format(message, act_message)
                assert message == act_message, err

            if over or ooc_over:
                assert(len(self.received_ooc) == 0)
            else:
                assert(len(self.received_ooc) != 0)

        def discard_all(self):
            self.received_commands = list()
            self.received_ooc = list()

        def receive_command_stc(self, command_type, *args):
            buffer = ''
            if command_type == 'decryptor': # Hi
                buffer = 'HI#FAKEHDID#%'
            elif command_type == 'ID': # Server ID
                buffer = "ID#AO2#2.4.8#%"
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
            else:
                raise KeyError('Unrecognized server argument {} {}'.format(command_type, args))

            if buffer:
                self.send_command_cts(buffer)

    def __init__(self, server):
        super().__init__(server, client_obj=self._TestClient)

    def new_client(self, transport, ip=None, my_protocol=None):
        if ip is None:
            ip = self.server.get_ipid("127.0.0.1")
        c = super().new_client(transport, client_obj=self._TestClient, ip=ip,
                               my_protocol=my_protocol)
        return c

class _TestAOProtocol(AOProtocol):
    def connection_made(self, transport, my_protocol=None):
        """ Called upon a new client connecting

        :param transport: the transport object
        """
        self.client = None
        self.ping_timeout = None

        super().connection_made(transport, my_protocol=my_protocol)

    def connection_lost(self, exc, client=None):
        """ User disconnected

        :param exc: reason
        """
        if not self.client:
            self.client = client
        self.server.remove_client(self.client)

        if self.ping_timeout:
            self.ping_timeout.cancel()

class _TestTsuserverDR(TsuserverDR):
    def __init__(self):
        super().__init__(client_manager=_TestClientManager, in_test=True)
        self.ao_protocol = _TestAOProtocol
        self.client_list = [None] * self.config['playerlimit']

    def create_client(self):
        new_ao_protocol = self.ao_protocol(self)
        new_ao_protocol.connection_made(None, my_protocol=new_ao_protocol)
        return new_ao_protocol.client

    def new_client(self, transport=None, my_protocol=None):
        c = self.client_manager.new_client(transport, my_protocol=my_protocol)
        if self.rp_mode:
            c.in_rp = True
        c.server = self
        c.area = self.area_manager.default_area()
        c.area.new_client(c)
        return c

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

    def make_clients(self, number, hdid_list=None, user_list=None):
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

        client.disconnect()
        if assert_no_outstanding:
            client.assert_no_packets()
            client.assert_no_ooc()
        self.client_list[client_id] = None

    def disconnect_all(self, assert_no_outstanding=False):
        for (i, client) in enumerate(self.client_list):
            if client:
                client.disconnect()
                if assert_no_outstanding:
                    client.assert_no_packets()
                    client.assert_no_ooc()
                self.client_list[i] = None