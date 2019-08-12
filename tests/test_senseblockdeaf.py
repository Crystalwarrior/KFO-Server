from .test_senseblock import _TestSenseBlock, _UnittestSenseBlock

class TestSenseBlockDeaf_01_Common(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'deafen'
        cls.sense_pp = 'deafened'
        cls.sense_attribute = lambda x, c: c.is_deaf

class TestSenseBlockDeaf_02_Effect(_TestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c3.move_area(5)

    def test_01_deafenC0(self):
        """
        Situation: C1 deafens C0.
        """

        self.c1.ooc('/deafen {}'.format(0))
        self.c1.assert_received_ooc('You have deafened {}.'.format(self.c0_charname), over=True)
        self.c0.assert_received_ooc('You have been deafened.', ooc_over=True)
        self.c2.assert_received_ooc('{} has deafened {} ({}).'
                                    .format(self.c1.name, self.c0_charname, 0), over=True)
        self.c3.assert_no_ooc()

        assert self.c0.is_deaf
        assert not self.c1.is_deaf
        assert not self.c2.is_deaf
        assert not self.c3.is_deaf

    def test_02_deafhearsnothing(self):
        """
        Situation: C0 and C1 talk to one another. C1 hears normally, C0 doesn't.
        """

        self.c0.sic('Hello?')
        self.c0.assert_received_ic('(Your ears are ringing)', folder=self.c0_charname,
                                   anim='happy', over=True)
        self.c1.assert_received_ic('Hello?', folder=self.c0_charname,
                                   anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c1.sic('Yes I can hear you.')
        self.c0.assert_received_ic('(Your ears are ringing)', folder=self.c1_charname,
                                   anim='happy', over=True)
        self.c1.assert_received_ic('Yes I can hear you.', folder=self.c1_charname,
                                   anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('I cant hear you :(')
        self.c0.assert_received_ic('(Your ears are ringing)', folder=self.c0_charname,
                                   anim='happy', over=True)
        self.c1.assert_received_ic('I cant hear you :(', folder=self.c0_charname,
                                   anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c2.sic('I still hear myself.')
        self.c2.assert_received_ic('I still hear myself.', folder=self.c2_charname,
                                   anim='happy', over=True)
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

    def test_03_deafchangesarea(self):
        """
        Situation: Deaf changes area and still hears nothing.
        """

        self.c0.move_area(4)

        self.c2.sic('Oi m8.')
        self.c0.assert_received_ic('(Your ears are ringing)', folder=self.c2_charname,
                                   anim='happy', over=True)
        self.c2.assert_received_ic('Oi m8.', folder=self.c2_charname,
                                   anim='happy', over=True)
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('Cant hear you.', anim='sad')
        self.c0.assert_received_ic('(Your ears are ringing)', folder=self.c0_charname,
                                   anim='sad', over=True)
        self.c2.assert_received_ic('Cant hear you.', folder=self.c0_charname,
                                   anim='sad', over=True)
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

    def test_04_deafhearspecialmessages(self):
        """
        Situation: Deaf can listen to messages that start with *, ( or [.
        """

        self.c0.sic('*attempts to listen.')
        self.c0.assert_received_ic('*attempts to listen.', folder=self.c0_charname, over=True)
        self.c2.assert_received_ic('*attempts to listen.', folder=self.c0_charname, over=True)

        self.c2.sic('((is confused about C0')
        self.c0.assert_received_ic('((is confused about C0', folder=self.c2_charname, over=True)
        self.c2.assert_received_ic('((is confused about C0', folder=self.c2_charname, over=True)

        self.c0.sic('[y r u liek dis')
        self.c0.assert_received_ic('[y r u liek dis', folder=self.c0_charname, over=True)
        self.c2.assert_received_ic('[y r u liek dis', folder=self.c0_charname, over=True)
