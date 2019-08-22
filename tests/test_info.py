from .test_ooc import _TestOOC

class TestInfo_01_Discord(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients use /discord incorrectly.
        """

        # Pass arguments
        self.c0.ooc('/discord e')
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_getdiscord(self):
        """
        Situation: Get the Discord link.
        """

        self.server.config['discord_link'] = 'https://www.example.com'

        self.c0.ooc('/discord')
        self.c0.assert_ooc('Discord Invite Link: https://www.example.com', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.server.config['discord_link'] = 'https://www.example.net'

        self.c1.ooc('/discord')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('Discord Invite Link: https://www.example.net', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

class TestInfo_02_MOTD(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients use /motd incorrectly.
        """

        # Pass arguments
        self.c0.ooc('/motd e')
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_getmotd(self):
        """
        Situation: Get the Message of the Day
        """
        mes = '=== MOTD ===\r\n{}\r\n============='.format(self.server.config['motd'])

        self.c0.ooc('/motd')
        self.c0.assert_ooc(mes, over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/motd')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc(mes, over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

class TestInfo_03_Online(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients use /online incorrectly.
        """

        # Pass arguments
        self.c0.ooc('/online e')
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_getonline(self):
        """
        Situation: Get the number of online players.
        """

        self.c0.ooc('/online')
        self.c0.assert_ooc('Online: {}/{}'.format(4, self.server.config['playerlimit']), over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/online')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('Online: {}/{}'.format(4, self.server.config['playerlimit']), over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.disconnect()

        self.c1.ooc('/online')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('Online: {}/{}'.format(3, self.server.config['playerlimit']), over=True)
        self.c3.assert_no_ooc()

        self.server.make_clients(4)

        self.c3.ooc('/online')
        self.c3.assert_ooc('Online: {}/{}'.format(7, self.server.config['playerlimit']), over=True)
        for c in self.server.client_manager.clients:
            if c == self.c3:
                continue
            c.assert_no_ooc()

class TestInfo_04_Ping(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /ping incorrectly.
        """

        self.c0.ooc('/ping a')
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_ping(self):
        """
        Situation: Clients attempt to test whether they are still connected.
        """

        for (n, c) in enumerate(self.clients[:4]):
            c.ooc('/ping')

            for i in range(4):
                if n == i:
                    self.clients[i].assert_ooc('Pong.', over=True)
                else:
                    self.clients[i].assert_no_ooc()