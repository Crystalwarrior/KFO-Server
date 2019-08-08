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
        self.c0.assert_received_ooc('You must insert a name with at least one letter.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/ping', username=' 1234 5678')
        self.c1.assert_received_ooc('You must insert a name with at least one letter.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # Username that starts with a space
        self.c0.ooc('Hello world.', username=' user0')
        self.c0.assert_received_ooc('You must insert a name that starts with a letter.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('Hello world.', username=' 1easfasf')
        self.c1.assert_received_ooc('You must insert a name that starts with a letter.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # Username with reserved name
        names0 = [self.server.config['hostname'], 'e{}'.format(self.server.config['hostname']),
                  'user1 <dollar>G e']
        names1 = ['<dollar>G', '{}<dollar>G', 'user 0 {}'.format(self.server.config['hostname'])]

        for name in names0:
            self.c0.ooc('Hello world.', username=name)
            self.c0.assert_received_ooc('That name is reserved.', over=True)
            self.c1.assert_no_ooc()
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

        for name in names1:
            self.c1.ooc('/pong.', username=name)
            self.c1.assert_received_ooc('That name is reserved.', over=True)
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
        self.c0.assert_received_ooc('Hello world.', username=self.c0.name, over=True)
        self.c1.assert_received_ooc('Hello world.', username=self.c0.name, over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('Hello world.')
        self.c0.assert_received_ooc('Hello world.', username=self.c1.name, over=True)
        self.c1.assert_received_ooc('Hello world.', username=self.c1.name, over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('Hello world?')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_received_ooc('Hello world?', username=self.c2.name, over=True)
        self.c3.assert_no_ooc()

        self.c3.ooc('Hello world!')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_received_ooc('Hello world!', username=self.c3.name, over=True)

    def test_03_samesends(self):
        """
        Situation: Clients send repeated OOC messages.
        """

        for i in range(5):
            message = 'Hello world {}.'.format(i)
            self.c0.ooc(message)
            self.c0.assert_received_ooc(message, username=self.c0.name, over=True)
            self.c1.assert_received_ooc(message, username=self.c0.name, over=True)
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

            self.c1.ooc(message)
            self.c0.assert_received_ooc(message, username=self.c1.name, over=True)
            self.c1.assert_received_ooc(message, username=self.c1.name, over=True)
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

        message = 'Hello world.'
        for i in range(5):
            self.c0.ooc(message)
            self.c0.assert_received_ooc(message, username=self.c0.name, over=True)
            self.c1.assert_received_ooc(message, username=self.c0.name, over=True)
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()

            self.c2.ooc(message)
            self.c0.assert_no_ooc()
            self.c1.assert_no_ooc()
            self.c2.assert_received_ooc(message, username=self.c2.name, over=True)
            self.c3.assert_no_ooc()

    def test_04_ping(self):
        """
        Situation: Clients attempt to test whether they are still connected.
        """

        self.c0.ooc('/ping a')
        self.c0.assert_received_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        for (n, c) in enumerate(self.clients[:4]):
            c.ooc('/ping')

            for i in range(4):
                if n == i:
                    self.clients[i].assert_received_ooc('Pong.', over=True)
                else:
                    self.clients[i].assert_no_ooc()

    def test_05_changename(self):
        """
        Situation: Client 0 changes their OOC name.
        """

        og_name = 'user0'

        self.c0.ooc('Hello world.')
        self.c0.assert_received_ooc('Hello world.', username=og_name, over=True)
        self.c1.assert_received_ooc('Hello world.', username=og_name, over=True)
        self.assertEqual(self.c0.name, og_name)

        new_name = 'user4'

        self.c0.ooc('Changed to {}.'.format(new_name), username=new_name)
        self.c0.assert_received_ooc('Changed to {}.'.format(new_name), username=new_name,
                                    over=True)
        self.c1.assert_received_ooc('Changed to {}.'.format(new_name), username=new_name,
                                    over=True)
        self.assertEqual(self.c0.name, new_name)

    def test_06_sameoocname(self):
        """
        Situation: Client 0 changes their OOC name to match... someone else's name, and it succeeds.
        Because apparently the code to check for OOC repetition was commented out.
        """

        new_name = self.c1.name

        self.c0.ooc('AAA', username=new_name)
        self.c0.assert_received_ooc('AAA', username=new_name, over=True)
        self.c1.assert_received_ooc('AAA', username=new_name, over=True)
        self.assertEqual(self.c0.name, new_name)

        self.c1.ooc('AAA')
        self.c0.assert_received_ooc('AAA', username=new_name, over=True)
        self.c1.assert_received_ooc('AAA', username=new_name, over=True)
        self.assertEqual(self.c0.name, new_name)

class TestOOC_02_PM(_TestOOC):
    def test_01_pmwrongarguments(self):
        """
        Situation: C0 attempts to PM incorrectly.
        """

        mes = ('Not enough arguments. Use /pm <target> <message>. Target should be ID, OOC-name or '
               'char-name. Use /getarea for getting info like "[ID] char-name".')

        # No target
        self.c0.ooc('/pm')
        self.c0.assert_received_ooc(mes, over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # No message
        self.c0.ooc('/pm 1')
        self.c0.assert_received_ooc(mes, over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # No target
        self.c0.ooc('/pm 100 Test')
        self.c0.assert_received_ooc('No targets found.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_sendpm(self):
        """
        Situation: Clients send pm to each other.
        """

        for c_a in self.clients[:4]:
            receipt = 'PM from {} in {} ({}): '.format(c_a.name, c_a.area.name, c_a.get_char_name())
            for c_b in self.clients[:4]:
                targets = [c_b.id]
                if c_a.area == c_b.area:
                    targets.extend([c_b.name, c_b.get_char_name()])

                target = random.choice(targets)
                sent = 'PM sent to {}. Message: '.format(target)
                message = '{}-->{}'.format(c_a.name, c_b.name)
                c_a.ooc('/pm {} {}'.format(target, message))
                c_a.assert_received_ooc(sent + message, over=(c_a!=c_b))
                c_b.assert_received_ooc(receipt + message, over=True)

    def test_03_otherareapm(self):
        """
        Situation: C0 attempts to PM C2 in another area, only succeeds when using cID 2.
        """

        receipt = ('PM from {} in {} ({}): '
                   .format(self.c0.name, self.c0.area.name, self.c0.get_char_name()))

        message = 'Works with cID.'
        self.c0.ooc('/pm 2 {}'.format(message))
        self.c0.assert_received_ooc('PM sent to 2. Message: {}'.format(message), over=True)
        self.c2.assert_received_ooc(receipt + message, over=True)
        self.c1.assert_no_ooc()
        self.c3.assert_no_ooc()

        message = 'Does not work with charname.'
        self.c0.ooc('/pm {} {}'.format(self.c2.get_char_name(), message))
        self.c0.assert_received_ooc('No targets found.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        message = 'Does not work with OOC name.'
        self.c0.ooc('/pm {} {}'.format(self.c2.name, message))
        self.c0.assert_received_ooc('No targets found.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_04_mutepm(self):
        """
        Situation: C0 mutes PMs.
        """

        self.c0.ooc('/mutepm e')
        self.c0.assert_received_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c0.ooc('/mutepm')
        self.c0.assert_received_ooc('You will no longer receive PMs.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)

        self.c0.ooc('/mutepm')
        self.c0.assert_received_ooc('You will now receive PMs.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertFalse(self.c0.pm_mute)

    def test_05_pmtomutedpm(self):
        """
        Situation: C1 and C0 attempt to PM one another, but fail as C0 has PMs muted.
        """
        self.c0.ooc('/mutepm')
        self.c0.assert_received_ooc('You will no longer receive PMs.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)

        self.c1.ooc('/pm 0 Hi')
        self.c1.assert_received_ooc('This user muted all PM conversations.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)

        self.c0.ooc('/pm 1 Hi')
        self.c0.assert_received_ooc('You have muted all PM conversations.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.pm_mute)

class TestOOC_03_Global(_TestOOC):
    def test_01_sendglobal(self):
        for (i, c) in enumerate(self.clients[:4]):
            c.ooc('/g Hello.')
            name = c.name
            area = c.area.id
            for x in self.clients[:4]:
                x.assert_received_ooc('Hello.', username='<dollar>G[{}][{}]'.format(area, name),
                                      over=True)