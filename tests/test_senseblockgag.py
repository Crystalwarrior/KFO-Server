from .test_senseblock import _TestSenseBlock, _UnittestSenseBlock

class TestSenseBlockGag_01_Common(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'gag'
        cls.sense_pp = 'gagged'
        cls.sense_attribute = lambda x, c: c.is_gagged

class TestSenseBlockGag_02_Effect(_TestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c3.move_area(5)

    def test_01_gagC0(self):
        """
        Situation: C1 gags C0.
        """

        self.c1.ooc('/gag {}'.format(0))
        self.c1.assert_ooc('You have gagged {}.'.format(self.c0_cname), over=True)
        self.c0.assert_ooc('You have been gagged.', ooc_over=True)
        self.c2.assert_ooc('{} has gagged {} ({}).'
                           .format(self.c1.name, self.c0_cname, 0), over=True)
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
        self.c0.assert_ic('(Gagged noises)', folder=self.c0_cname, anim='happy', over=True)
        self.c1.assert_ooc('{} tried to say "{}" but is currently gagged.'
                           .format(self.c0_cname, 'Hello?'), ooc_over=True)
        self.c1.assert_ic('(Gagged noises)', folder=self.c0_cname, anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c1.sic('I cant understand you.')
        self.c0.assert_ic('I cant understand you.', folder=self.c1_cname, anim='happy', over=True)
        self.c1.assert_ic('I cant understand you.', folder=self.c1_cname, anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('Mood', anim='mood')
        self.c0.assert_ic('(Gagged noises)', folder=self.c0_cname, anim='mood', over=True)
        self.c1.assert_ooc('{} tried to say "{}" but is currently gagged.'
                           .format(self.c0_cname, 'Mood'), ooc_over=True)
        self.c1.assert_ic('(Gagged noises)', folder=self.c0_cname, anim='mood', over=True)
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
        self.c2.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)
        self.c3.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)
        self.c1.assert_no_ic()

        self.c0.sic('Im gagged.', anim='sad')
        self.c0.assert_ic('(Gagged noises)', folder=self.c0_cname, anim='sad', over=True)
        self.c2.assert_ooc('{} tried to say "{}" but is currently gagged.'
                           .format(self.c0_cname, 'Im gagged.'), ooc_over=True)
        self.c2.assert_ic('(Gagged noises)', folder=self.c0_cname,
                          anim='sad', over=True)
        self.c3.assert_ic('(Gagged noises)', folder=self.c0_cname, anim='sad', over=True)
        self.c3.assert_no_ic()

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
