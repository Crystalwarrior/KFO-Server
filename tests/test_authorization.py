import datetime
import time

from .structures import _TestSituation3, _TestSituation4, _TestSituation5


class _TestAuthorization(_TestSituation3):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guardpass = cls.server.config['guardpass']
        cls.modpass = cls.server.config['modpass']
        cls.cmpass = cls.server.config['cmpass']
        cls.gmpass = cls.server.config['gmpass']
        cls.gmpasses = [None] * 8
        cls.gmpasses[1] = cls.server.config['gmpass1']
        cls.gmpasses[2] = cls.server.config['gmpass2']
        cls.gmpasses[3] = cls.server.config['gmpass3']
        cls.gmpasses[4] = cls.server.config['gmpass4']
        cls.gmpasses[5] = cls.server.config['gmpass5']
        cls.gmpasses[6] = cls.server.config['gmpass6']
        cls.gmpasses[7] = cls.server.config['gmpass7']
        cls.wrong = "AAAABBBB"  # Please do not make this any of your staff passwords

        current_day = datetime.datetime.today().weekday()
        cls.daily_gmpass = cls.server.config['gmpass{}'.format((current_day % 7) + 1)]
        cls.not_daily_gmpasses = {cls.server.config['gmpass{}'.format((x % 7) + 1)]
                                  for x in range(1, 7) if x != current_day}

        cls.all_passwords = {cls.wrong,
                             cls.wrong,
                             cls.gmpass,
                             cls.daily_gmpass,
                             cls.cmpass,
                             cls.modpass,
                             cls.guardpass}.union(cls.not_daily_gmpasses)
        cls.wrong_passwords = cls.all_passwords.copy()  # Set by child tests

    def test_01_NoClientLoggedinYet(self):
        """
        Situation: Everyone should not be logged in at server bootup.
        """
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)
            # self.assertTrue(c.in_rp) # Assumes server starts with RP mode on


class _TestAuthorizationSingleRank(_TestAuthorization):
    def test_02_WrongLogin(self):
        """
        Situation: C0 attempts to log in to the rank with a variety of wrong passwords.
        """

        # Try and log in with incorrect passwords
        for password in self.wrong_passwords:
            self.c0.ooc('/{} {}'.format(self.ooc_command, password))
            self.c0.assert_ooc('Invalid password.', over=True)
            self.assertFalse(self.good_rank(self.c0))

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(self.good_rank(c))
            self.assertFalse(self.bad_rank1(c))
            self.assertFalse(self.bad_rank2(c))
            # self.assertTrue(c.in_rp) # Assumes server starts with RP mode on

    def test_03_RightLoginAndRelogin(self):
        """
        Situation: C0 logs in successfully with the rank, and attempts to relogin.
        """

        self.c0.ooc('/{} {}'.format(self.ooc_command, self.correct_pass1))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc(self.ooc_successful_login, over=True)
        self.assertTrue(self.good_rank(self.c0))

        self.c0.ooc('/{} {}'.format(self.ooc_command, self.correct_pass1))
        self.c0.assert_ooc('Already logged in.', over=True)
        self.assertTrue(self.good_rank(self.c0))

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(self.good_rank(c)) if c != self.c0 else None
            self.assertFalse(self.bad_rank1(c))
            self.assertFalse(self.bad_rank2(c))

    def test_04_LogoutAndRelogout(self):
        """
        Situation: C0 attempts to log out of their rank.
        """

        self.c0.ooc('/logout {}'.format(self.correct_pass1))  # Some argument
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.assertTrue(self.good_rank(self.c0))

        self.c0.ooc('/logout')
        self.c0.assert_ooc('You are no longer logged in.', ooc_over=True)
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None, over=True)
        self.assertFalse(self.good_rank(self.c0))

        self.c0.ooc('/logout')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.assertFalse(self.good_rank(self.c0))

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(self.good_rank(c))
            self.assertFalse(self.bad_rank1(c))
            self.assertFalse(self.bad_rank2(c))

    def test_05_LoginLogout(self):
        """
        Situation: C0 logs in and out of their rank, once with password 1, once with password 2.
        """

        self.c0.ooc('/{} {}'.format(self.ooc_command, self.correct_pass1))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc(self.ooc_successful_login, over=True)
        self.assertTrue(self.good_rank(self.c0))

        self.c0.ooc('/logout')
        self.c0.assert_ooc('You are no longer logged in.', ooc_over=True)
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None, over=True)
        self.assertFalse(self.good_rank(self.c0))

        self.c0.ooc('/{} {}'.format(self.ooc_command, self.correct_pass2))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc(self.ooc_successful_login, over=True)
        self.assertTrue(self.good_rank(self.c0))

        self.c0.ooc('/logout')
        self.c0.assert_ooc('You are no longer logged in.', ooc_over=True)
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None, over=True)
        self.assertFalse(self.good_rank(self.c0))

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(self.good_rank(c))
            self.assertFalse(self.bad_rank1(c))
            self.assertFalse(self.bad_rank2(c))

    def test_06_TwoSimultaneousSameRank(self):
        """
        Situation: Two players attempt to log in and log out to the same rank using a combination
        of passwords 1 and 2 in a variety of orders.
        """

        pass_pos = ([self.correct_pass1, self.correct_pass1],
                    [self.correct_pass1, self.correct_pass2],
                    [self.correct_pass2, self.correct_pass1],
                    [self.correct_pass2, self.correct_pass2])
        client_pos = ([self.c0, self.c1, self.c0, self.c1], [self.c0, self.c1, self.c1, self.c0],
                      [self.c1, self.c0, self.c1, self.c0], [self.c1, self.c0, self.c0, self.c1])

        for [pass1, pass2] in pass_pos:
            for (a1, a2, b1, b2) in client_pos:
                a1.ooc('/{} {}'.format(self.ooc_command, pass1))
                a1.assert_packet('FA', None)
                a1.assert_packet('FM', None)
                a1.assert_ooc(self.ooc_successful_login, over=True)
                self.assertTrue(self.good_rank(a1))
                self.assertFalse(self.good_rank(a2))
                a2.ooc('/{} {}'.format(self.ooc_command, pass2))
                a2.assert_packet('FA', None)
                a2.assert_packet('FM', None)
                a2.assert_ooc(self.ooc_successful_login, over=True)
                self.assertTrue(self.good_rank(a1))
                self.assertTrue(self.good_rank(a2))

                # Assert the login message a1 got from a2 logging in
                # Also log the state of a1 for later use
                if a1.is_mod:
                    a1.assert_ooc('{} [{}] logged in as a moderator.'
                                  .format(a2.name, a2.id), over=True)
                elif a1.is_cm:
                    a1.assert_ooc('{} [{}] logged in as a community manager.'
                                  .format(a2.name, a2.id), over=True)

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(self.good_rank(c)) if c == self.c2 else None
                    self.assertFalse(self.bad_rank1(c))
                    self.assertFalse(self.bad_rank2(c))

                b1.ooc('/logout')
                b1.assert_ooc('You are no longer logged in.', ooc_over=True)
                b1.assert_packet('FA', None)
                b1.assert_packet('FM', None, over=True)
                self.assertFalse(self.good_rank(b1))
                self.assertTrue(self.good_rank(b2))
                if b2.is_mod:
                    b2.assert_ooc('{} [{}] is no longer a moderator.'
                                  .format(b1.name, b1.id), over=True)
                elif b2.is_cm:
                    b2.assert_ooc('{} [{}] is no longer a community manager.'
                                  .format(b1.name, b1.id), over=True)
                b2.ooc('/logout')
                b2.assert_ooc('You are no longer logged in.', ooc_over=True)
                b2.assert_packet('FA', None)
                b2.assert_packet('FM', None, over=True)
                self.assertFalse(self.good_rank(b1))
                self.assertFalse(self.good_rank(b2))

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(self.good_rank(c))
                    self.assertFalse(self.bad_rank1(c))
                    self.assertFalse(self.bad_rank2(c))

    def test_07_OneRankedInOneRankedOut(self):
        """
        Situation: Two players attempt to log in and log out using a combination of passwords 1
        and 2 in a variety of orders, but one gets it wrong.
        """

        pass_pos = ([self.correct_pass1, self.wrong],
                    [self.correct_pass2, self.wrong])
        client_pos = ([self.c0, self.c1, self.c0, self.c1], [self.c0, self.c1, self.c1, self.c0],
                      [self.c1, self.c0, self.c1, self.c0], [self.c1, self.c0, self.c0, self.c1])

        for [pass1, pass2] in pass_pos:
            for (a1, a2, b1, b2) in client_pos:
                a1.ooc('/{} {}'.format(self.ooc_command, pass1))
                a1.assert_packet('FA', None)
                a1.assert_packet('FM', None)
                a1.assert_ooc(self.ooc_successful_login, over=True)
                self.assertTrue(self.good_rank(a1))
                self.assertFalse(self.good_rank(a2))
                a2.ooc('/{} {}'.format(self.ooc_command, pass2))
                a2.assert_ooc('Invalid password.', over=True)
                self.assertTrue(self.good_rank(a1))
                self.assertFalse(self.good_rank(a2))
                if a1.is_mod:
                    a1.assert_ooc('{} [{}] failed to login as a moderator.'
                                  .format(a2.name, a2.id), over=True)
                elif a1.is_cm:
                    a1.assert_ooc('{} [{}] failed to login as a community manager.'
                                  .format(a2.name, a2.id), over=True)

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(self.good_rank(c)) if c == self.c2 else None
                    self.assertFalse(self.bad_rank1(c))
                    self.assertFalse(self.bad_rank2(c))
                if self.good_rank(b1):
                    b1.ooc('/logout')
                    b1.assert_ooc('You are no longer logged in.', ooc_over=True)
                    b1.assert_packet('FA', None)
                    b1.assert_packet('FM', None, over=True)
                else:
                    b1.ooc('/logout')
                    b1.assert_ooc('You must be authorized to do that.', ooc_over=True)

                if a1 == b1:
                    self.assertFalse(self.good_rank(a1))
                else:
                    self.assertTrue(self.good_rank(a1))
                self.assertFalse(self.good_rank(a2))
                if self.good_rank(b2):
                    b2.ooc('/logout')
                    b2.assert_ooc('You are no longer logged in.', ooc_over=True)
                    b2.assert_packet('FA', None)
                    b2.assert_packet('FM', None, over=True)
                else:
                    b2.ooc('/logout')
                    b2.assert_ooc('You must be authorized to do that.', ooc_over=True)
                self.assertFalse(self.good_rank(b1))
                self.assertFalse(self.good_rank(b2))

                # Make sure no one is randomly logged in either
                for c in self.clients[:3]:
                    self.assertFalse(self.good_rank(c))
                    self.assertFalse(self.bad_rank1(c))
                    self.assertFalse(self.bad_rank2(c))


class TestAuthorization_01_GMBasic(_TestAuthorizationSingleRank):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ooc_command = "loginrp"
        cls.ooc_successful_login = 'Logged in as a game master.'
        cls.correct_pass1 = cls.gmpass
        cls.correct_pass2 = cls.daily_gmpass
        cls.wrong_passwords -= {cls.gmpass, cls.daily_gmpass}
        cls.good_rank = lambda x, c: c.is_gm
        cls.bad_rank1 = lambda x, c: c.is_mod
        cls.bad_rank2 = lambda x, c: c.is_cm


class TestAuthorization_02_CMBasic(_TestAuthorizationSingleRank):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ooc_command = "logincm"
        cls.ooc_successful_login = 'Logged in as a community manager.'
        cls.correct_pass1 = cls.cmpass
        cls.correct_pass2 = cls.cmpass
        cls.wrong_passwords -= {cls.cmpass}
        cls.good_rank = lambda x, c: c.is_cm
        cls.bad_rank1 = lambda x, c: c.is_mod
        cls.bad_rank2 = lambda x, c: c.is_gm


class TestAuthorization_03_ModBasic(_TestAuthorizationSingleRank):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ooc_command = "login"
        cls.ooc_successful_login = 'Logged in as a moderator.'
        cls.correct_pass1 = cls.modpass
        cls.correct_pass2 = cls.modpass
        cls.wrong_passwords -= {cls.modpass}
        cls.good_rank = lambda x, c: c.is_mod
        cls.bad_rank1 = lambda x, c: c.is_cm
        cls.bad_rank2 = lambda x, c: c.is_gm


class TestAuthorization_04_Integration(_TestAuthorization):
    def test_02_WrongLogins(self):
        """
        Situation: C0-2 attempt to log in to different ranks with wrong passwords.
        """

        # Try and log in with incorrect passwords
        self.c0.ooc('/logincm {}'.format(self.wrong))
        self.c0.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c0.is_cm)

        self.c1.ooc('/loginrp {}'.format(self.wrong))
        self.c1.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c1.is_gm)

        self.c0.ooc('/login {}'.format(self.wrong))
        self.c0.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c0.is_mod)

        self.c1.ooc('/login {}'.format(self.wrong))
        self.c1.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c1.is_mod)

        self.c2.ooc('/loginrp {}'.format(self.wrong))
        self.c2.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c2.is_gm)

        self.c1.ooc('/logincm {}'.format(self.wrong))
        self.c1.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c1.is_cm)

        self.c0.ooc('/login {}'.format(self.wrong))
        self.c0.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c0.is_gm)

        self.c2.ooc('/loginrp {}'.format(self.wrong))
        self.c2.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c2.is_gm)

        self.c2.ooc('/logincm {}'.format(self.wrong))
        self.c2.assert_ooc('Invalid password.', over=True)
        self.assertFalse(self.c2.is_cm)

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)

    def test_03_RightLoginAndRelogin(self):
        """
        Situation: C0-2 log in successfully with the rank, and attempt to relogin.
        """

        self.c1.ooc('/logincm {}'.format(self.cmpass))
        self.c1.assert_packet('FA', None)
        self.c1.assert_packet('FM', None)
        self.c1.assert_ooc('Logged in as a community manager.', over=True)
        self.assertTrue(self.c1.is_cm)

        self.c0.ooc('/loginrp {}'.format(self.gmpass))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc('Logged in as a game master.', over=True)
        self.c1.assert_ooc('{} [{}] logged in as a game master with the global password.'
                           .format(self.c0.name, self.c0.id), over=True)
        self.assertTrue(self.c0.is_gm)

        self.c0.ooc('/loginrp {}'.format(self.gmpass))
        self.c0.assert_ooc('Already logged in.', over=True)
        self.assertTrue(self.c0.is_gm)

        self.c2.ooc('/login {}'.format(self.modpass))
        self.c2.assert_packet('FA', None)
        self.c2.assert_packet('FM', None)
        self.c2.assert_ooc('Logged in as a moderator.', over=True)
        self.c1.assert_ooc('{} [{}] logged in as a moderator.'
                           .format(self.c2.name, self.c2.id), over=True)
        self.assertTrue(self.c2.is_mod)

        self.c2.ooc('/login {}'.format(self.modpass))
        self.c2.assert_ooc('Already logged in.', over=True)
        self.assertTrue(self.c2.is_mod)

        self.c1.ooc('/logincm {}'.format(self.cmpass))
        self.c1.assert_ooc('Already logged in.', over=True)
        self.assertTrue(self.c1.is_cm)

    def test_04_LogoutAndRelogout(self):
        """
        Situation: C0-2 attempt to log out of their rank in some order.
        """

        self.c0.ooc('/logout {}'.format(self.gmpass))  # Some argument
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.assertTrue(self.c0.is_gm)

        self.c0.ooc('/logout')
        self.c0.assert_ooc('You are no longer logged in.', ooc_over=True)
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None, over=True)
        self.c1.assert_ooc('{} [{}] is no longer a game master.'
                           .format(self.c0.name, self.c0.id), over=True)
        self.c2.assert_ooc('{} [{}] is no longer a game master.'
                           .format(self.c0.name, self.c0.id), over=True)
        self.assertFalse(self.c0.is_gm)
        self.assertTrue(self.c1.is_cm)
        self.assertTrue(self.c2.is_mod)

        self.c0.ooc('/logout')
        self.c0.assert_ooc('You must be authorized to do that.', ooc_over=True)
        self.assertFalse(self.c0.is_gm)
        self.assertTrue(self.c1.is_cm)
        self.assertTrue(self.c2.is_mod)

        self.c2.ooc('/logout {}'.format(self.wrong))  # Some argument
        self.c2.assert_ooc('This command has no arguments.', over=True)
        self.assertFalse(self.c0.is_gm)
        self.assertTrue(self.c1.is_cm)
        self.assertTrue(self.c2.is_mod)

        self.c1.ooc('/logout')
        self.c1.assert_ooc('You are no longer logged in.', ooc_over=True)
        self.c1.assert_packet('FA', None)
        self.c1.assert_packet('FM', None, over=True)
        self.c2.assert_ooc('{} [{}] is no longer a community manager.'
                           .format(self.c1.name, self.c1.id), over=True)
        self.assertFalse(self.c0.is_gm)
        self.assertFalse(self.c1.is_cm)
        self.assertTrue(self.c2.is_mod)

        self.c2.ooc('/logout')
        self.c2.assert_ooc('You are no longer logged in.', ooc_over=True)
        self.c2.assert_packet('FA', None)
        self.c2.assert_packet('FM', None, over=True)
        self.assertFalse(self.c0.is_gm)
        self.assertFalse(self.c1.is_cm)
        self.assertFalse(self.c2.is_mod)

        self.c1.ooc('/logout {}'.format(self.wrong))  # Some argument
        # Staff restriction is checked before arguments
        self.c1.assert_ooc('You must be authorized to do that.', over=True)
        self.assertFalse(self.c0.is_gm)
        self.assertFalse(self.c1.is_cm)
        self.assertFalse(self.c2.is_mod)

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)

    def test_05_LoginLogout(self):
        """
        Situation: C0-2 log in and out of their rank, once with password 1, once with password 2,
        in a variety of orders.
        """
        def login(c1, c2, ooc_rank1, ooc_rank2, pass1, pass2, rank1, rank2, success1, success2):
            c1.ooc('/{} {}'.format(ooc_rank1, pass1))
            c1.assert_packet('FA', None)
            c1.assert_packet('FM', None)
            c1.assert_ooc(success1, over=True)
            self.assertTrue(rank1(c1))

            c1.ooc('/logout')
            c1.assert_ooc('You are no longer logged in.', ooc_over=True)
            c1.assert_packet('FA', None)
            c1.assert_packet('FM', None, over=True)
            self.assertFalse(rank1(c1))

            c2.ooc('/{} {}'.format(ooc_rank2, pass2))
            c2.assert_packet('FA', None)
            c2.assert_packet('FM', None)
            c2.assert_ooc(success2, over=True)
            self.assertTrue(rank2(c2))

            c2.ooc('/logout')
            c2.assert_ooc('You are no longer logged in.', ooc_over=True)
            c2.assert_packet('FA', None)
            c2.assert_packet('FM', None, over=True)
            self.assertFalse(rank2(c2))

        x0, x1, x2 = self.c0, self.c1, self.c2
        oocmod, ooccm, oocgm = "login", "logincm", "loginrp"
        pmod, pcm, pgm1, pgm2 = self.modpass, self.cmpass, self.gmpass, self.daily_gmpass
        rankmod, rankcm, rankgm = lambda c: c.is_mod, lambda c: c.is_cm, lambda c: c.is_gm
        smod, scm, sgm = ('Logged in as a moderator.',
                          'Logged in as a community manager.',
                          'Logged in as a game master.')

        sit = [(x0, x1, oocmod, ooccm, pmod, pcm, rankmod, rankcm, smod, scm),
               (x2, x0, oocgm, oocgm, pgm1, pgm2, rankgm, rankgm, sgm, sgm),
               (x1, x2, oocmod, oocgm, pmod, pgm2, rankmod, rankgm, smod, sgm),
               (x2, x0, ooccm, oocmod, pcm, pmod, rankcm, rankmod, scm, smod),
               (x1, x1, oocgm, ooccm, pgm1, pcm, rankgm, rankcm, sgm, scm),
               (x0, x2, ooccm, oocmod, pcm, pmod, rankcm, rankmod, scm, smod)]

        for (c1, c2, ooc_rank1, ooc_rank2, pass1, pass2, rank1, rank2, success1, success2) in sit:
            login(c1, c2, ooc_rank1, ooc_rank2, pass1, pass2, rank1, rank2, success1, success2)

        # Make sure no one is randomly logged in either
        for c in self.clients[:3]:
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)

    def test_06_OneSingleRankPerPlayer(self):
        """
        Situation: A player attempts to log in to multiple ranks simultaneously.
        """

        self.c0.ooc('/loginrp {}'.format(self.gmpass))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc('Logged in as a game master.', over=True)
        self.assertFalse(self.c0.is_mod)
        self.assertFalse(self.c0.is_cm)
        self.assertTrue(self.c0.is_gm)

        self.c0.ooc('/logincm {}'.format(self.cmpass))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc('Logged in as a community manager.', over=True)
        self.assertFalse(self.c0.is_mod)
        self.assertTrue(self.c0.is_cm)
        self.assertFalse(self.c0.is_gm)

        self.c0.ooc('/login {}'.format(self.modpass))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc('Logged in as a moderator.', over=True)
        self.assertTrue(self.c0.is_mod)
        self.assertFalse(self.c0.is_cm)
        self.assertFalse(self.c0.is_gm)

        self.c0.ooc('/loginrp {}'.format(self.daily_gmpass))
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc('Logged in as a game master.', over=True)
        self.assertFalse(self.c0.is_mod)
        self.assertFalse(self.c0.is_cm)
        self.assertTrue(self.c0.is_gm)

    def test_07_DisconnectionRemovesRank(self):
        """
        Situation: C0-2 log out individually and relogin, without their rank.
        """

        for i in range(2):
            self.server.disconnect_client(i)
            self.server.make_clients(1)
            c = self.clients[i]
            self.assertFalse(c.is_mod)
            self.assertFalse(c.is_cm)
            self.assertFalse(c.is_gm)


class TestAuthorization_05_Shortcuts(_TestAuthorization):
    """
    Tester of authorization shortcuts.
    """

    def test_02_IndividualShortcuts(self):
        """
        Situation: C0 logs in as GM, C1 as GM, C2 as mod, and they all log out, all in some order.
        """

        self.c2.make_mod()
        self.assertTrue(not self.c0.is_mod and not self.c0.is_gm and not self.c0.is_cm)
        self.assertTrue(not self.c1.is_mod and not self.c1.is_gm and not self.c1.is_cm)
        self.assertTrue(self.c2.is_mod and not self.c2.is_gm and not self.c2.is_cm)

        self.c1.make_cm()
        self.assertTrue(not self.c0.is_mod and not self.c0.is_gm and not self.c0.is_cm)
        self.assertTrue(self.c1.is_cm and not self.c1.is_gm and not self.c1.is_mod)
        self.assertTrue(self.c2.is_mod and not self.c2.is_gm and not self.c2.is_cm)

        self.c1.make_normie()
        self.assertTrue(not self.c0.is_gm and not self.c0.is_cm and not self.c0.is_mod)
        self.assertTrue(not self.c1.is_mod and not self.c1.is_cm and not self.c1.is_gm)
        self.assertTrue(self.c2.is_mod and not self.c2.is_gm and not self.c2.is_cm)

        self.c0.make_gm()
        self.assertTrue(self.c0.is_gm and not self.c0.is_cm and not self.c0.is_mod)
        self.assertTrue(not self.c1.is_cm and not self.c1.is_gm and not self.c1.is_mod)
        self.assertTrue(self.c2.is_mod and not self.c2.is_gm and not self.c2.is_cm)

        self.c2.make_normie()
        self.assertTrue(self.c0.is_gm and not self.c0.is_cm and not self.c0.is_mod)
        self.assertTrue(not self.c1.is_mod and not self.c1.is_cm and not self.c1.is_gm)
        self.assertTrue(not self.c2.is_mod and not self.c2.is_cm and not self.c2.is_gm)

        self.c0.make_normie()
        self.assertTrue(not self.c0.is_mod and not self.c0.is_cm and not self.c0.is_gm)
        self.assertTrue(not self.c1.is_mod and not self.c1.is_cm and not self.c1.is_gm)
        self.assertTrue(not self.c2.is_mod and not self.c2.is_cm and not self.c2.is_gm)

    def test_03_IndividualRelogging(self):
        """
        Situation: C0-2 relog multiple times.
        """

        self.c0.make_gm()
        self.c0.make_cm()
        self.c0.make_mod()
        self.c0.make_cm()
        self.assertTrue(self.c0.is_cm and not self.c0.is_gm and not self.c0.is_mod)
        self.assertTrue(not self.c1.is_mod and not self.c1.is_cm and not self.c1.is_gm)
        self.assertTrue(not self.c2.is_mod and not self.c2.is_cm and not self.c2.is_gm)

        self.c2.make_mod()
        self.c2.make_cm()
        self.c2.make_cm()
        self.c2.make_mod()
        self.assertTrue(self.c0.is_cm and not self.c0.is_gm and not self.c0.is_mod)
        self.assertTrue(not self.c1.is_gm and not self.c1.is_cm and not self.c1.is_mod)
        self.assertTrue(self.c2.is_mod and not self.c2.is_cm and not self.c2.is_gm)

        self.c1.make_mod()
        self.c1.make_cm()
        self.c1.make_gm()
        self.c1.make_gm()
        self.assertTrue(self.c0.is_cm and not self.c0.is_gm and not self.c0.is_mod)
        self.assertTrue(self.c1.is_gm and not self.c1.is_cm and not self.c1.is_mod)
        self.assertTrue(self.c2.is_mod and not self.c2.is_cm and not self.c2.is_gm)


class TestAuthorization_06_GMSelf(_TestSituation4):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.c0.make_mod()
        self.c1.make_cm()
        self.c2.make_gm()
        self.c0.move_area(5)
        self.c1.move_area(6)
        self.c2.move_area(6)
        self.c0.ipid = 2
        self.c1.ipid = 1
        self.c2.ipid = 2
        self.c3.ipid = 3
        self.c0.hdid = '0'
        self.c1.hdid = '1'
        self.c2.hdid = '2'
        self.c3.hdid = '2'

    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /gmself incorrectly.
        """

        # Non-staff
        self.c3.ooc('/gmself')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_ooc('You must be authorized to do that.', over=True)

        # Parameters
        self.c2.ooc('/gmself 1000')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('This command has no arguments.', over=True)
        self.c3.assert_no_packets()

    def test_02_gmselfmorethanone(self):
        """
        Situation: C2 uses /gmself. Its multiclients C0 and C3 are now forcefully logged in as GM,
        even in the case of C0 who was a mod. C1 sees nothing.
        """

        self.c2.ooc('/gmself')
        self.c0.assert_packet('FA', None)
        self.c0.assert_packet('FM', None)
        self.c0.assert_ooc('Logged in as a game master.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Logged in clients {} and {} as game master.'.format(0, 3), over=True)
        self.c3.assert_packet('FA', None)
        self.c3.assert_packet('FM', None)
        self.c3.assert_ooc('Logged in as a game master.', over=True)

        self.assertTrue(self.c0.is_gm and not self.c0.is_cm and not self.c0.is_mod)
        self.assertTrue(self.c1.is_cm and not self.c1.is_gm and not self.c1.is_mod)
        self.assertTrue(self.c2.is_gm and not self.c2.is_cm and not self.c2.is_mod)
        self.assertTrue(self.c3.is_gm and not self.c3.is_cm and not self.c3.is_mod)

    def test_03_gmselfnone(self):
        """
        Situation: C2 uses /gmself. Its multiclients C0 and C3 are already GM, so C0 gets an error.
        C1 sees nothing.
        """

        self.c2.ooc('/gmself')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('All opened clients are already logged in as game master.', over=True)
        self.c3.assert_no_packets()

        self.assertTrue(self.c0.is_gm and not self.c0.is_cm and not self.c0.is_mod)
        self.assertTrue(self.c1.is_cm and not self.c1.is_gm and not self.c1.is_mod)
        self.assertTrue(self.c2.is_gm and not self.c2.is_cm and not self.c2.is_mod)
        self.assertTrue(self.c3.is_gm and not self.c3.is_cm and not self.c3.is_mod)

    def test_04_multiclientusesgmself(self):
        """
        Situation: C2 logs out. C0 uses /gmself. Therefore, C2 is logged in. C1 and C3 see nothing.
        """

        self.c2.make_normie()

        self.c0.ooc('/gmself')
        self.c0.assert_ooc('Logged in client {} as game master.'.format(2), over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('FA', None)
        self.c2.assert_packet('FM', None)
        self.c2.assert_ooc('Logged in as a game master.', over=True)
        self.c3.assert_no_packets()


class TestAuthorization_07_Effect(_TestSituation5):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.c0.make_mod()
        self.c1.make_cm()
        self.c2.make_gm()
        self.c0.move_area(5)
        self.c1.move_area(6)
        self.c2.move_area(6)
        self.c3.move_area(7)
        self.c4.move_area(5)

    def do_modcall(self, client, recipients, cname, cipid, aname, aid):
        client.send_command_cts('ZZ#%')
        current_time = time.strftime("%H:%M", time.localtime())
        client.assert_ooc('You have called for a moderator.', ooc_over=True)

        for c in self.server.get_clients():
            if c not in recipients:
                c.assert_no_packets()
                continue
            c.assert_packet('ZZ', ('[{}] {} ({}) called for a moderator in {} ({}).'
                                   .format(current_time, cname, cipid, aname, aid)), over=True)

    def test_01_modcall(self):
        """
        Situation: Various players call for mod. Only mods and CMs receive notifications.
        """

        self.do_modcall(self.c3, {self.c0, self.c1}, self.c3_cname, self.c3.ipid, self.area7.name,
                        self.area7.id)
        self.do_modcall(self.c4, {self.c0, self.c1}, self.c4_cname, self.c4.ipid, self.area5.name,
                        self.area5.id)
        self.do_modcall(self.c0, {self.c0, self.c1}, self.c0_cname, self.c0.ipid, self.area5.name,
                        self.area5.id)

        self.c2.make_mod()
        self.do_modcall(self.c2, {self.c0, self.c1, self.c2}, self.c2_cname, self.c2.ipid,
                        self.area6.name, self.area6.id)

        self.c1.make_normie()
        self.do_modcall(self.c1, {self.c0, self.c2}, self.c1_cname, self.c1.ipid, self.area6.name,
                        self.area6.id)

        self.c1.send_command_cts('ZZ#%')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You must wait 30 seconds between mod calls.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
