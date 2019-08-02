import asyncio

from server.aoprotocol import AOProtocol
from server.client_manager import ClientManager
from server.tsuserver import TsuserverDR

class _TestClientManager(ClientManager):
    class _TestClient(ClientManager.Client):
        def __init__(self, *args):
            super().__init__(*args)
            self.received_commands = list()
            self.received_ooc = list()
            self.my_protocol = None

        def disconnect(self):
            self.my_protocol.connection_lost(None)

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

    def new_client(self, transport):
        cur_id = 0
        for i in range(self.server.config['playerlimit']):
            if not self.cur_id[i]:
                cur_id = i
                break
        c = self._TestClient(self.server, transport, cur_id, self.server.get_ipid("127.0.0.1"))
        self.clients.add(c)
        self.cur_id[cur_id] = True
        self.server.client_tasks[cur_id] = dict()
        return c

class _TestAOProtocol(AOProtocol):
    def connection_made(self, transport, my_protocol=None):
        """ Called upon a new client connecting

        :param transport: the transport object
        """
        self.client = self.server.new_client(transport)
        self.client.my_protocol = my_protocol
        self.ping_timeout = asyncio.get_event_loop().call_later(self.server.config['timeout'], self.client.disconnect)
        self.client.send_command_stc('decryptor', 34)  # just fantacrypt things

class _TestTsuserverDR(TsuserverDR):
    def __init__(self):
        super().__init__(client_manager=_TestClientManager)
        self.ao_protocol = _TestAOProtocol

    def create_client(self):
        new_ao_protocol = self.ao_protocol(self)
        new_ao_protocol.connection_made(None, my_protocol=new_ao_protocol)
        return new_ao_protocol.client

    def new_client(self, transport=None):
        c = self.client_manager.new_client(transport)
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

        c.send_command_cts("CC#{}#{}#{}#%"
                           .format(c.id, char_id, hdid))
        exp = self.char_list[char_id]
        res = c.get_char_name()
        assert exp == res, (char_id, exp, res)
        c.discard_all()

        return c