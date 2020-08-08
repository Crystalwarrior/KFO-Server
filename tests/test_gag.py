from .structures import _TestSituation5Mc1Gc2
from .test_senseblock import _TestSenseBlock, _UnittestSenseBlock

class _TestGag(_TestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c3.move_area(5)

    @staticmethod
    def _is_gagged_message(msg):
        if not 5+1 <= len(msg) <= 9+1:
            return False
        if not msg.startswith(('G', 'M')):
            return False
        non_letters = [x for x in msg[1:] if x not in ['g', 'h', 'r', 'm']]
        if non_letters:
            return False
        return True

    def assert_ic_gag(self, client, over=False, ic_over=False, check_MS_packet=True, **kwargs):
        # Assert client received a valid gagged message, then continue with assert_ic method
        assert(len(client.received_ic) > 0)
        params = client.received_ic[0]
        param_id_msg = 4 # Change if later protocol changes this
        msg = params[param_id_msg]

        if not self._is_gagged_message(msg):
            raise AssertionError('{} expected a gagged message, received {}'.format(client, msg))

        client.assert_ic(msg, over=over, ic_over=ic_over, check_MS_packet=check_MS_packet, **kwargs)

class TestGag_01_Common(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'gag'
        cls.sense_pp = 'gagged'
        cls.sense_attribute = lambda x, c: c.is_gagged

class TestGag_02_Effect(_TestGag):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c3.move_area(5)

    def test_01_gagC0(self):
        """
        Situation: C1 gags C0.
        """

        self.c1.ooc('/gag {}'.format(0))
        self.c1.assert_ooc('You have gagged {}.'.format(self.c0_dname), over=True)
        self.c0.assert_ooc('You have been gagged.', ooc_over=True)
        self.c2.assert_ooc('(X) {} [{}] has gagged {} ({}).'
                           .format(self.c1.displayname, 1, self.c0_dname, 0), over=True)
        self.c3.assert_no_ooc()

        assert self.c0.is_gagged
        assert not self.c1.is_gagged
        assert not self.c2.is_gagged
        assert not self.c3.is_gagged

    def test_02_gaggedsaysnothing(self):
        """
        Situation: C0 and C1 talk to one another. C1 hears normally, C0 doesn't.
        """

        self.c0.sic('Hello?')
        self.assert_ic_gag(self.c0, folder=self.c0_cname, anim='happy', over=True)
        self.c1.assert_ooc('(X) {} [{}] tried to say `{}` but is currently gagged.'
                           .format(self.c0_dname, 0, 'Hello?'), ooc_over=True)
        self.assert_ic_gag(self.c1, folder=self.c0_cname, anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c1.sic('I cant understand you.')
        self.c0.assert_ic('I cant understand you.', folder=self.c1_cname, anim='happy', over=True)
        self.c1.assert_ic('I cant understand you.', folder=self.c1_cname, anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('Mood', anim='mood')
        self.assert_ic_gag(self.c0, folder=self.c0_cname, anim='mood', over=True)
        self.c1.assert_ooc('(X) {} [{}] tried to say `{}` but is currently gagged.'
                           .format(self.c0_dname, 0, 'Mood'), ooc_over=True)
        self.assert_ic_gag(self.c1, folder=self.c0_cname, anim='mood', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c2.sic('I can still talk myself.')
        self.c2.assert_ic('I can still talk myself.', folder=self.c2_cname, anim='happy', over=True)
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

    def test_03_gaggedchangesarea(self):
        """
        Situation: Gagged changes area and still can say nothing.
        """

        self.c0.move_area(4)
        self.c3.move_area(4)

        self.c2.sic('Oi m8.')
        self.c0.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)
        self.c1.assert_no_ic()
        self.c2.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)
        self.c3.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)

        self.c0.sic('Im gagged.', anim='sad')
        self.assert_ic_gag(self.c0, folder=self.c0_cname, anim='sad', over=True)
        self.c1.assert_no_ic()
        self.c2.assert_ooc('(X) {} [{}] tried to say `{}` but is currently gagged.'
                           .format(self.c0_dname, 0, 'Im gagged.'), ooc_over=True)
        self.assert_ic_gag(self.c2,  folder=self.c0_cname,
                          anim='sad', over=True)
        self.assert_ic_gag(self.c3, folder=self.c0_cname, anim='sad', over=True)

    def test_04_gaggedsaysspecialmessages(self):
        """
        Situation: Gagged players can send messages that start with *, ( or [.
        """

        self.c0.sic('*attempts to talk.')
        self.c0.assert_ic('*attempts to talk.', folder=self.c0_cname, over=True)
        self.c2.assert_ic('*attempts to talk.', folder=self.c0_cname, over=True)
        self.c3.assert_ic('*attempts to talk.', folder=self.c0_cname, over=True)

        self.c2.sic('((is confused about C0')
        self.c0.assert_ic('((is confused about C0', folder=self.c2_cname, over=True)
        self.c2.assert_ic('((is confused about C0', folder=self.c2_cname, over=True)
        self.c3.assert_ic('((is confused about C0', folder=self.c2_cname, over=True)

        self.c0.sic('[y r u liek dis')
        self.c0.assert_ic('[y r u liek dis', folder=self.c0_cname, over=True)
        self.c2.assert_ic('[y r u liek dis', folder=self.c0_cname, over=True)
        self.c3.assert_ic('[y r u liek dis', folder=self.c0_cname, over=True)

class TestGag_03_Miscellaneous(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.ooc('/gag 0')

        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()

    def test_01_gaggedspecial(self):
        """
        Situation: C0 attempts to scream. Does not go that well.
        """

        self.area0.scream_range = set([self.area5.name])
        self.c2.move_area(5)
        self.c3.move_area(5)

        self.c0.ooc('/scream Hi')
        self.c0.assert_ooc('You attempted to scream but you have no mouth.', over=True)
        self.c1.assert_ooc('(X) {} [{}] attempted to scream "Hi" while gagged ({}).'
                           .format(self.c0_dname, 0, 0), over=True)
        self.c2.assert_ooc('(X) {} [{}] attempted to scream "Hi" while gagged ({}).'
                           .format(self.c0_dname, 0, 0), over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_ooc('You hear some grunting noises.', over=True)