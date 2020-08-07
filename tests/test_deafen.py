from .test_senseblock import _TestSenseBlock, _UnittestSenseBlock

class _TestDeafen(_TestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c3.move_area(5)

    def convo1(self):
        self.c2.sic('Oi m8.')
        self.c0.assert_ic('(Your ears are ringing)', folder=self.c2_cname, anim='happy', over=True)
        self.c2.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)

        others = [self.c1, self.c3]
        if self.server.client_list[4]:
            others.append(self.server.client_list[4])

        for c in others:
            if c.area == self.c0.area:
                c.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)
            else:
                c.assert_no_ic()

        self.c0.sic('Cant hear you.', anim='sad')
        self.c0.assert_ic('(Your ears are ringing) ', folder=self.c0_cname, anim='sad', over=True)
        self.c2.assert_ic('Cant hear you.', folder=self.c0_cname, anim='sad', over=True)

        for c in others:
            if c.area == self.c0.area:
                c.assert_ic('Cant hear you.', folder=self.c0_cname, anim='sad', over=True)
            else:
                c.assert_no_ic()

class TestDeafen_01_Common(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'deafen'
        cls.sense_pp = 'deafened'
        cls.sense_attribute = lambda x, c: c.is_deaf

class TestDeafen_02_Effect(_TestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c3.move_area(5)

    def test_01_deafenC0(self):
        """
        Situation: C1 deafens C0.
        """

        self.c1.ooc('/deafen {}'.format(0))
        self.c1.assert_ooc('You have deafened {}.'.format(self.c0_dname), over=True)
        self.c0.assert_ooc('You have been deafened.', ooc_over=True)
        self.c2.assert_ooc('(X) {} [{}] has deafened {} ({}).'
                           .format(self.c1.displayname, 1, self.c0_dname, 0), over=True)
        self.c3.assert_no_ooc()

        assert self.c0.is_deaf
        assert not self.c1.is_deaf
        assert not self.c2.is_deaf
        assert not self.c3.is_deaf

    def test_02_deafhearsnothing(self):
        """
        Situation: C0 and C1 talk to one another. C1 hears normally, C0 doesn't.
        """
        # Note that some messages have extra spaces
        # That is because AO filters out messages with repetitions

        self.c0.sic('Hello?')
        self.c0.assert_ic('(Your ears are ringing)', folder=self.c0_cname, anim='happy', over=True)
        self.c1.assert_ic('Hello?', folder=self.c0_cname, anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c1.sic('Yes I can hear you.')
        self.c0.assert_ic('(Your ears are ringing) ', folder=self.c1_cname, anim='happy', over=True)
        self.c1.assert_ic('Yes I can hear you.', folder=self.c1_cname, anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('I cant hear you :(')
        self.c0.assert_ic('(Your ears are ringing)', folder=self.c0_cname, anim='happy', over=True)
        self.c1.assert_ic('I cant hear you :(', folder=self.c0_cname, anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c2.sic('I still hear myself.')
        self.c2.assert_ic('I still hear myself.', folder=self.c2_cname, anim='happy', over=True)
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

    def test_03_deafchangesarea(self):
        """
        Situation: Deaf changes area and still hears nothing.
        """

        self.c0.move_area(4)

        self.c2.sic('Oi m8.')
        self.c0.assert_ic('(Your ears are ringing) ', folder=self.c2_cname, anim='happy', over=True)
        self.c2.assert_ic('Oi m8.', folder=self.c2_cname, anim='happy', over=True)
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('Cant hear you.', anim='sad')
        self.c0.assert_ic('(Your ears are ringing)', folder=self.c0_cname, anim='sad', over=True)
        self.c2.assert_ic('Cant hear you.', folder=self.c0_cname, anim='sad', over=True)
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

    def test_04_deafhearspecialmessages(self):
        """
        Situation: Deaf can listen to messages that start with *, ( or [.
        """

        self.c0.sic('*attempts to listen.')
        self.c0.assert_ic('*attempts to listen.', folder=self.c0_cname, over=True)
        self.c2.assert_ic('*attempts to listen.', folder=self.c0_cname, over=True)

        self.c2.sic('((is confused about C0')
        self.c0.assert_ic('((is confused about C0', folder=self.c2_cname, over=True)
        self.c2.assert_ic('((is confused about C0', folder=self.c2_cname, over=True)

        self.c0.sic('[y r u liek dis')
        self.c0.assert_ic('[y r u liek dis', folder=self.c0_cname, over=True)
        self.c2.assert_ic('[y r u liek dis', folder=self.c0_cname, over=True)

class TestDeafen_03_ChangeArea(_TestDeafen):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.ooc('/deafen 0')
        cls.c0.move_area(4)
        cls.c1.move_area(4)
        cls.server.make_clients(1)
        cls.c4 = cls.clients[4]
        cls.c4.ooc('/switch {}'.format(cls.server.config['spectator_name']))
        cls.c4.move_area(4)
        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()
        cls.c4.discard_all()

    def test_01_deafandlights(self):
        """
        Situation:
        1. C2 turns lights off. C0 notices the lights off.
        2. C0 leaves room while lights are off and gets notif of light status when they return.
        3. C3 comes to the room and gets notif of lights out. C0 gets no steps notification.
        4. C2 turns lights on. C0 and C3 does notice light change.
        """

        self.c2.ooc('/lights off')
        self.c0.assert_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_ooc('The lights were turned off.', over=True)
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()
        self.convo1()

        self.c0.move_area(5, discard_trivial=True)
        self.c0.assert_no_ooc()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()
        self.c0.move_area(4, discard_trivial=True)
        self.c0.assert_ooc('You enter a pitch dark room.', over=True)
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()

        self.c3.move_area(4)
        self.c0.assert_no_ooc()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()

        self.c2.ooc('/lights on')
        self.c0.assert_packet('BN', self.c0.area.background)
        self.c0.assert_ooc('The lights were turned on.', over=True)
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()
        self.convo1()

    def test_02_deafandautopass(self):
        """
        Situation: C3, with autopass moves to area 5 and then back. C0 gets normal autopass message.
        """

        self.c3.ooc('/autopass')
        self.c3.move_area(5)
        self.c0.assert_ooc('{} has left to the {}'.format(self.c3_dname, self.a5_name), over=True)

        self.c3.move_area(4)
        self.c0.assert_ooc('{} has entered from the {}'
                           .format(self.c3_dname, self.a5_name), over=True)

        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()

    def test_03_deafandautopassnolight(self):
        """
        Situation: Autopass and lights off. C0 only notices lights off, but no autopass nor
        footsteps in or out.
        """

        self.c3.ooc('/lights off')
        self.c0.assert_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_ooc('The lights were turned off.', over=True)

        self.c3.move_area(5)
        self.c0.assert_no_ooc()

        self.c3.move_area(4)
        self.c0.assert_no_ooc()

        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()

class TestDeafen_04_Miscellaneous(_TestDeafen):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.ooc('/deafen 0')

        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()

    def test_01_screamringsears(self):
        """
        Situation: C3 in another area screams. C0 gets nerfed message.
        """

        self.area5.scream_range = set([self.area0.name])

        self.c3.ooc('/scream Hi')
        self.c0.assert_no_ooc()
        self.c0.assert_ic('(Your ears are ringing)', over=True)
        self.c1.assert_ooc('(X) {} [{}] screamed "Hi" ({}).'
                           .format(self.c3_dname, 3, 5), ooc_over=True)
        self.c1.assert_ic('Hi', over=True)
        self.c2.assert_ooc('(X) {} [{}] screamed "Hi" ({}).'
                           .format(self.c3_dname, 3, 5), over=True)
        self.c2.assert_no_ic() # C2 is not in scream range
        self.c3.assert_ooc('You screamed "Hi".', ooc_over=True)
        self.c3.assert_ic('Hi', over=True)

    def test_02_globalicringssears(self):
        """
        Situation: C2 uses /globalic to talk to people in area 0. C0 gets (Your ears are ringing).
        """

        self.c2.ooc('/globalic 0')
        self.c2.assert_ooc('Your IC messages will now be sent to area {}.'
                           .format(self.a0_name))
        self.c2.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)

        self.c2.sic('Hi')
        self.c0.assert_ic('(Your ears are ringing) ', folder=self.c2_cname, over=True)
        self.c1.assert_ic('Hi', folder=self.c2_cname, over=True)
        self.c2.assert_ooc('Sent global IC message "Hi" to area {}.'
                           .format(self.a0_name), over=True)

        self.c2.ooc('/globalic 0, 1')
        self.c2.assert_ooc('Your IC messages will now be sent to areas {} through {}.'
                           .format(self.a0_name, self.a1_name))
        self.c2.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)

        self.c2.sic('Hi.')
        self.c0.assert_ic('(Your ears are ringing)', folder=self.c2_cname, over=True) # client wk
        self.c1.assert_ic('Hi.', folder=self.c2_cname, over=True)
        self.c2.assert_ooc('Sent global IC message "Hi." to areas {} through {}.'
                           .format(self.a0_name, self.a1_name), over=True)

    def test_03_noknock(self):
        """
        Situation: C0 moves out of lobby. C3 uses /knock on C0's area. C0 gets nothing.
        """

        self.c0.move_area(6)

        self.c3.ooc('/knock {}'.format(6))
        self.c0.assert_no_ooc()
        self.c0.assert_ic('', ding=0, over=True)
        self.c1.assert_ooc('(X) {} [{}] knocked on the door to area {} in area {} ({}).'
                           .format(self.c3_dname, 3, self.a6_name, self.a5_name, 5), over=True)
        self.c1.assert_no_ic()
        self.c2.assert_ooc('(X) {} [{}] knocked on the door to area {} in area {} ({}).'
                           .format(self.c3_dname, 3, self.a6_name, self.a5_name, 5), over=True)
        self.c2.assert_no_ic()
        self.c3.assert_ooc('You knocked on the door to area {}.'.format(self.a6_name),
                           ooc_over=True)
        self.c3.assert_ic('', ding=7, over=True)
