import datetime

from .structures import _Unittest

class TestGMAuthorization(_Unittest):
    def setUp(self):
        self.server.make_clients(3)
        self.guardpass = self.server.config['guardpass']
        self.modpass = self.server.config['modpass']
        self.cmpass = self.server.config['cmpass']
        self.gmpass = self.server.config['gmpass']
        self.gmpasses = [None] * 8
        self.gmpasses[1] = self.server.config['gmpass1']
        self.gmpasses[2] = self.server.config['gmpass2']
        self.gmpasses[3] = self.server.config['gmpass3']
        self.gmpasses[4] = self.server.config['gmpass4']
        self.gmpasses[5] = self.server.config['gmpass5']
        self.gmpasses[6] = self.server.config['gmpass6']
        self.gmpasses[7] = self.server.config['gmpass7']
        self.c0 = self.clients[0]
        self.c1 = self.clients[1]
        self.c2 = self.clients[2]
        self.host = self.server.config['hostname']
        self.wrong = "AAAABBBB" # Please do not make this any of your staff passwords

        current_day = datetime.datetime.today().weekday()
        if datetime.datetime.now().hour < 15:
            current_day += 1
        self.daily_gmpass = self.server.config['gmpass{}'.format((current_day % 7) + 1)]
        self.not_daily_gmpasses = [self.server.config['gmpass{}'.format(((current_day + x)% 7) + 1)]
                                   for x in range(1, 7)]

    def test_01_NoClientLoggedinYet(self):
        """
        Situation: Everyone should not be logged in at server bootup.
        """

        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)
            #print(self.server.rp_mode)
            #self.assertTrue(c.in_rp) # Assumes server starts with RP mode on

    def test_02_GMWrongLogin(self):
        """
        Situation: C0 attempts to log in as game master with a variety of wrong passwords.
        """

        wrong_passwords = [self.wrong,
                           self.wrong,
                           self.cmpass,
                           self.modpass,
                           self.guardpass] + self.not_daily_gmpasses

        # Try and log in with incorrect passwords
        for password in wrong_passwords:
            self.c0.ooc('/loginrp {}'.format(password))
            self.c0.assert_received_ooc(self.host, 'Invalid password.', over=True)
            self.assertFalse(self.c0.is_gm)

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)
            #print(self.server.rp_mode)
            #self.assertTrue(c.in_rp) # Assumes server starts with RP mode on

    def test_03_GMRightLoginAndRelogin(self):
        """
        Situation: C0 logs in successfully as game master, and attempts to relogin.
        """

        self.c0.ooc('/loginrp {}'.format(self.gmpass))
        self.c0.assert_received_packet('FM', None)
        self.c0.assert_received_ooc(self.host, 'Logged in as a game master.', over=True)
        self.assertTrue(self.c0.is_gm)

        self.c0.ooc('/loginrp {}'.format(self.gmpass))
        self.c0.assert_received_ooc(self.host, 'Already logged in.', over=True)
        self.assertTrue(self.c0.is_gm)

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm) if c != self.c0 else None

    def test_04_GMLogoutAndRelogout(self):
        """
        Situation: C0 attempts to log out as game master.
        """

        self.c0.ooc('/logout {}'.format(self.gmpass)) # Some argument
        self.c0.assert_received_ooc(self.host, 'This command has no arguments.', over=True)
        self.assertTrue(self.c0.is_gm)

        self.c0.ooc('/logout')
        self.c0.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
        self.c0.assert_received_packet('FM', None, over=True)
        self.assertFalse(self.c0.is_gm)

        self.c0.ooc('/logout')
        self.c0.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
        self.c0.assert_received_packet('FM', None, over=True)
        self.assertFalse(self.c0.is_gm)

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)

    def test_05_GMLoginLogout(self):
        """
        Situation: C0 logs in and out of game master, once with gmpass, once with daily pass.
        """

        self.c0.ooc('/loginrp {}'.format(self.gmpass))
        self.c0.assert_received_packet('FM', None)
        self.c0.assert_received_ooc(self.host, 'Logged in as a game master.', over=True)
        self.assertTrue(self.c0.is_gm)

        self.c0.ooc('/logout')
        self.c0.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
        self.c0.assert_received_packet('FM', None, over=True)
        self.assertFalse(self.c0.is_gm)

        self.c0.ooc('/loginrp {}'.format(self.daily_gmpass))
        self.c0.assert_received_packet('FM', None)
        self.c0.assert_received_ooc(self.host, 'Logged in as a game master.', over=True)
        self.assertTrue(self.c0.is_gm)

        self.c0.ooc('/logout')
        self.c0.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
        self.c0.assert_received_packet('FM', None, over=True)
        self.assertFalse(self.c0.is_gm)

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)

    def test_06_TwoSimultaneousGMs(self):
        """
        Situation: Two players attempt to log in and log out using a combination of gmpass and
        daily gmpass in a variety of orders.
        """

        pass_pos = ([self.gmpass, self.gmpass], [self.daily_gmpass, self.gmpass],
                    [self.gmpass, self.daily_gmpass], [self.daily_gmpass, self.daily_gmpass])
        client_pos = ([self.c0, self.c1, self.c0, self.c1], [self.c0, self.c1, self.c1, self.c0],
                      [self.c1, self.c0, self.c1, self.c0], [self.c1, self.c0, self.c0, self.c1])

        for [pass1, pass2] in pass_pos:
            for (a1, a2, b1, b2) in client_pos:
                a1.ooc('/loginrp {}'.format(pass1))
                a1.assert_received_packet('FM', None)
                a1.assert_received_ooc(self.host, 'Logged in as a game master.', over=True)
                self.assertTrue(a1.is_gm)
                self.assertFalse(a2.is_gm)
                a2.ooc('/loginrp {}'.format(pass2))
                a2.assert_received_packet('FM', None)
                a2.assert_received_ooc(self.host, 'Logged in as a game master.', over=True)
                self.assertTrue(a1.is_gm)
                self.assertTrue(a2.is_gm)

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(c.is_mod)
                    self.assertFalse(c.is_cm)
                    self.assertFalse(c.is_gm) if c == self.c2 else None

                b1.ooc('/logout')
                b1.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
                b1.assert_received_packet('FM', None, over=True)
                self.assertFalse(b1.is_gm)
                self.assertTrue(b2.is_gm)
                b2.ooc('/logout')
                b2.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
                b2.assert_received_packet('FM', None, over=True)
                self.assertFalse(b1.is_gm)
                self.assertFalse(b1.is_gm)

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(c.is_mod)
                    self.assertFalse(c.is_cm)
                    self.assertFalse(c.is_gm)

    def test_07_OneGMInOneGmOut(self):
        """
        Situation: Two players attempt to log in and log out using a combination of gmpass and
        daily gmpass in a variety of orders, but one gets it wrong.
        """

        pass_pos = ([self.gmpass, self.wrong], [self.daily_gmpass, self.wrong])
        client_pos = ([self.c0, self.c1, self.c0, self.c1], [self.c0, self.c1, self.c1, self.c0],
                      [self.c1, self.c0, self.c1, self.c0], [self.c1, self.c0, self.c0, self.c1])

        for [pass1, pass2] in pass_pos:
            for (a1, a2, b1, b2) in client_pos:
                a1.ooc('/loginrp {}'.format(pass1))
                a1.assert_received_packet('FM', None)
                a1.assert_received_ooc(self.host, 'Logged in as a game master.', over=True)
                self.assertTrue(a1.is_gm)
                self.assertFalse(a2.is_gm)
                a2.ooc('/loginrp {}'.format(pass2))
                a2.assert_received_ooc(self.host, 'Invalid password.', over=True)
                self.assertTrue(a1.is_gm)
                self.assertFalse(a2.is_gm)

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(c.is_mod)
                    self.assertFalse(c.is_cm)
                    self.assertFalse(c.is_gm) if c == self.c2 else None

                b1.ooc('/logout')
                b1.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
                b1.assert_received_packet('FM', None, over=True)
                if a1 == b1:
                    self.assertFalse(a1.is_gm)
                else:
                    self.assertTrue(a1.is_gm)
                self.assertFalse(a2.is_gm)
                b2.ooc('/logout')
                b2.assert_received_ooc(self.host, 'You are no longer logged in.', ooc_over=True)
                b2.assert_received_packet('FM', None, over=True)
                self.assertFalse(b1.is_gm)
                self.assertFalse(b1.is_gm)

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(c.is_mod)
                    self.assertFalse(c.is_cm)
                    self.assertFalse(c.is_gm)
