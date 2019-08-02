import asyncio
import unittest

from server.aoprotocol import AOProtocol
from server.client_manager import ClientManager
from server.tsuserver import TsuserverDR

class _Unittest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print('Testing {}...'.format(__file__))
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
        self.clients = None

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
            self.received_commands.append([command_type, args])
            self.receive_command_stc(command_type, *args)

        def send_command_cts(self, buffer):
            self.my_protocol.data_received(buffer.encode('utf-8'))

        def assert_no_packets(self):
            assert(len(self.received_commands) == 0)

        def assert_received_packet(self, command_type, args, over=False):
            assert(len(self.received_commands) > 0)
            exp_command_type, exp_args = self.received_commands.pop(0)
            assert(command_type == exp_command_type)
            if isinstance(args, tuple):
                assert(len(args) == len(exp_args))
                for i, arg in enumerate(args):
                    if arg is None:
                        continue
                    assert arg == exp_args[i], (command_type, i, arg, exp_args[i])

            if over:
                assert(len(self.received_commands) == 0)
            else:
                assert(len(self.received_commands) != 0)

        def assert_no_ooc(self):
            assert(len(self.received_ooc) == 0)

        def assert_received_ooc(self, username, message, over=False):
            assert(len(self.received_ooc) > 0)
            exp_username, exp_message = self.received_ooc.pop(0)
            if username:
                assert(exp_username == username)
            if message:
                assert(exp_message == message)

            if over:
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
        super().__init__(client_manager=_TestClientManager)
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

    def make_clients(self, number, hdid_list=None):
        if hdid_list is None:
            hdid_list = ['FAKEHDID'] * number
        else:
            assert len(hdid_list) == number

        for i in range(number):
            area = self.area_manager.default_area()
            for j in range(len(self.char_list)):
                if area.is_char_available(j):
                    char_id = j
                    break
            else:
                char_id = -1

            client = self.make_client(char_id, hdid=hdid_list[i])
            for j, existing_client in enumerate(self.client_list):
                if existing_client is None:
                    self.client_list[j] = client
                    break
            else:
                j = -1
            assert j == client.id, (j, client.id)

    def disconnect_all(self, assert_no_outstanding=False):
        for (i, client) in enumerate(self.client_list):
            if client:
                client.disconnect()
                if assert_no_outstanding:
                    client.assert_no_packets()
                    client.assert_no_ooc()
                self.client_list[i] = None
