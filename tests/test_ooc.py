import random

from .structures import _TestSituation4Mc1Gc2

class _TestOOC(_TestSituation4Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(5)

class TestOOC_01_Basic(_TestOOC):
    def test_01_invaliduser(self):
        """
        Situation: Clients try to send messages/commands with invalid usernames.
        """

        old_name0 = self.c0.name
        old_name1 = self.c1.name

        # No letters case
        self.c0.ooc('Hello world.', username=' ')
        self.c0.assert_ooc('You must insert a name with at least one letter.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/ping', username=' 1234 5678')
        self.c1.assert_ooc('You must insert a name with at least one letter.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # Username that starts with a space
        self.c0.ooc('Hello world.', username=' user0')
        self.c0.assert_ooc('You must insert a name that starts with a letter.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('Hello world.', username=' 1easfasf')
        self.c1.assert_ooc('You must insert a name that starts with a letter.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # Username with reserved name
        names0 = [self.server.config['hostname'], 'e{}'.format(self.server.config['hostname']),
                  'user1 <dollar>G e']
        names1 = ['<dollar>G', '{}<dollar>G', 'user 0 {}'.format(self.server.config['hostname'])]

        for name in names0:
            self.c0.ooc('Hello world.', username=name)
            self.c0.assert_ooc('That name is reserved.', over=True)
            self.c1.assert_no_ooc()
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

        for name in names1:
            self.c1.ooc('/pong.', username=name)
            self.c1.assert_ooc('That name is reserved.', over=True)
            self.c0.assert_no_ooc()
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

        self.c0.name = old_name0
        self.c1.name = old_name1

    def test_02_usermessage(self):
        """
        Situation: Each client sends an OOC message.
        """

        self.c0.ooc('Hello world.')
        self.c0.assert_ooc('Hello world.', username=self.c0.name, over=True)
        self.c1.assert_ooc('Hello world.', username=self.c0.name, over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('Hello world.')
        self.c0.assert_ooc('Hello world.', username=self.c1.name, over=True)
        self.c1.assert_ooc('Hello world.', username=self.c1.name, over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('Hello world?')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Hello world?', username=self.c2.name, over=True)
        self.c3.assert_no_ooc()

        self.c3.ooc('Hello world!')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_ooc('Hello world!', username=self.c3.name, over=True)

    def test_03_samesends(self):
        """
        Situation: Clients send repeated OOC messages.
        """

        for i in range(5):
            message = 'Hello world {}.'.format(i)
            self.c0.ooc(message)
            self.c0.assert_ooc(message, username=self.c0.name, over=True)
            self.c1.assert_ooc(message, username=self.c0.name, over=True)
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

            self.c1.ooc(message)
            self.c0.assert_ooc(message, username=self.c1.name, over=True)
            self.c1.assert_ooc(message, username=self.c1.name, over=True)
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

        message = 'Hello world.'
        for i in range(5):
            self.c0.ooc(message)
            self.c0.assert_ooc(message, username=self.c0.name, over=True)
            self.c1.assert_ooc(message, username=self.c0.name, over=True)
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

            self.c2.ooc(message)
            self.c0.assert_no_ooc()
            self.c1.assert_no_ooc()
            self.c2.assert_ooc(message, username=self.c2.name, over=True)
            self.c3.assert_no_ooc()

    def test_04_changename(self):
        """
        Situation: Client 0 changes their OOC name.
        """

        og_name = 'user0'

        self.c0.ooc('Hello world.')
        self.c0.assert_ooc('Hello world.', username=og_name, over=True)
        self.c1.assert_ooc('Hello world.', username=og_name, over=True)
        self.assertEqual(self.c0.name, og_name)

        new_name = 'user4'

        self.c0.ooc('Changed to {}.'.format(new_name), username=new_name)
        self.c0.assert_ooc('Changed to {}.'.format(new_name), username=new_name, over=True)
        self.c1.assert_ooc('Changed to {}.'.format(new_name), username=new_name, over=True)
        self.assertEqual(self.c0.name, new_name)

    def test_05_sameoocname(self):
        """
        Situation: Client 0 changes their OOC name to match... someone else's name, and it succeeds.
        Because apparently the code to check for OOC repetition was commented out.
        """

        new_name = self.c1.name

        self.c0.ooc('AAA', username=new_name)
        self.c0.assert_ooc('AAA', username=new_name, over=True)
        self.c1.assert_ooc('AAA', username=new_name, over=True)
        self.assertEqual(self.c0.name, new_name)

        self.c1.ooc('AAA')
        self.c0.assert_ooc('AAA', username=new_name, over=True)
        self.c1.assert_ooc('AAA', username=new_name, over=True)
        self.assertEqual(self.c0.name, new_name)

class TestOOC_02_PM(_TestOOC):
    def test_01_pmwrongarguments(self):
        """
        Situation: C0 attempts to PM incorrectly.
        """

        mes = ('Not enough arguments. Use /pm <target> <message>. Target should be '
               'ID, char-name, edited-to character, custom showname or OOC-name.')

        # No target
        self.c0.ooc('/pm')
        self.c0.assert_ooc(mes, over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # No message
        self.c0.ooc('/pm 1')
        self.c0.assert_ooc(mes, over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # No target
        self.c0.ooc('/pm 100 Test')
        self.c0.assert_ooc('No targets with identifier `100 Test` found.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_sendpm(self):
        """
        Situation: Clients send pm to each other.
        """

        for c_a in self.clients[:4]:
            receipt = 'PM from {} in {} ({}): '.format(c_a.name, c_a.area.name, c_a.displayname)
            for c_b in self.clients[:4]:
                targets = [c_b.id]
                if c_a.area == c_b.area:
                    targets.extend([c_b.name, c_b.displayname])

                for target in targets:
                    sent = 'PM sent to {}. Message: '.format(target)
                    message = '{}-->{}'.format(c_a.name, c_b.name)
                    c_a.ooc('/pm {} {}'.format(target, message))
                    c_a.assert_ooc(sent + message, over=(c_a!=c_b))
                    c_b.assert_ooc(receipt + message, over=True)

    def test_03_otherareapm(self):
        """
        Situation: C0 attempts to PM C2 in another area, only succeeds when using cID 2.
        """

        receipt = ('PM from {} in {} ({}): '
                   .format(self.c0.name, self.c0.area.name, self.c0.displayname))

        message = 'Works with cID.'
        self.c0.ooc('/pm 2 {}'.format(message))
        self.c0.assert_ooc('PM sent to 2. Message: {}'.format(message), over=True)
        self.c2.assert_ooc(receipt + message, over=True)
        self.c1.assert_no_ooc()
        self.c3.assert_no_ooc()

        message = 'Does not work with charname.'
        self.c0.ooc('/pm {} {}'.format(self.c2.get_char_name(), message))
        self.c0.assert_ooc('No targets with identifier `Maki Harukawa_HD Does not work with '
                           'charname.` found.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        message = 'Does not work with OOC name.'
        self.c0.ooc('/pm {} {}'.format(self.c2.name, message))
        self.c0.assert_ooc('No targets with identifier `user2 Does not work with OOC name.` found.',
                           over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

class TestOOC_03_TogglePM(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Clients attempt to use /toggle_pm incorrectly.
        """

        # Pass arguments
        self.c0.ooc('/toggle_pm e')
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_usetogglepm(self):
        """
        Situation: C0 uses /toggle_pm repeatedly.
        """

        self.c0.ooc('/toggle_pm')
        self.c0.assert_ooc('You will no longer receive PMs.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)

        self.c0.ooc('/toggle_pm')
        self.c0.assert_ooc('You will now receive PMs.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertFalse(self.c0.pm_mute)

    def test_03_pmtomutedpm(self):
        """
        Situation: C0 mutes PMs and C1 and C0 attempt to PM one another. They both fail.
        """

        self.c0.ooc('/toggle_pm')
        self.c0.assert_ooc('You will no longer receive PMs.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)

        self.c1.ooc('/pm 0 Hi')
        self.c1.assert_ooc('This user muted all PM conversations.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)

        self.c0.ooc('/pm 1 Hi')
        self.c0.assert_ooc('You have muted all PM conversations.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)
