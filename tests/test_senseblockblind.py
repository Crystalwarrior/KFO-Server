from .test_senseblock import _TestSenseBlock, _UnittestSenseBlock

class _TestSenseBlockBlind(_TestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c3.move_area(5)

    def convo1(self):
        self.c2.sic('Oi m8.')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('Oi m8.', folder=self.c2_cname,
                                   anim='../../misc/blank', over=True)
        self.c2.assert_received_ic('Oi m8.', folder=self.c2_cname,
                                   anim='happy', over=True)

        others = [self.c1, self.c3]
        if self.server.client_list[4]:
            others.append(self.server.client_list[4])

        for c in others:
            if c.area == self.c0.area:
                c.assert_received_ic('Oi m8.', folder=self.c2_cname,
                                           anim='happy', over=True)
            else:
                c.assert_no_ic()

        self.c0.sic('Cant see you.', anim='sad')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('Cant see you.', folder=self.c0_cname,
                                   anim='../../misc/blank', over=True)
        self.c2.assert_received_ic('Cant see you.', folder=self.c0_cname,
                                   anim='sad', over=True)

        for c in others:
            if c.area == self.c0.area:
                c.assert_received_ic('Cant see you.', folder=self.c0_cname,
                                     anim='sad', over=True)
            else:
                c.assert_no_ic()


class TestSenseBlockBlind_01_Common(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'blind'
        cls.sense_pp = 'blinded'
        cls.sense_attribute = lambda x, c: c.is_blind

    def sense_affect(self, client):
        if client.is_blind:
            client.assert_received_packet('BN', self.server.config['blackout_background'],
                                          over=True)
        else:
            raise TypeError

    def sense_unaffect(self, client):
        if not client.is_blind:
            client.assert_received_packet('BN', client.area.background, over=True)
        else:
            raise TypeError

class TestSenseBlockBlind_02_Effect(_TestSenseBlockBlind):
    def test_01_blindC0(self):
        """
        Situation: C1 blinds C0.
        """

        self.c1.ooc('/blind {}'.format(0))
        self.c1.assert_received_ooc('You have blinded {}.'.format(self.c0_cname), over=True)
        self.c0.assert_received_ooc('You have been blinded.', ooc_over=True)
        self.c2.assert_received_ooc('{} has blinded {} ({}).'
                                    .format(self.c1.name, self.c0_cname, 0), over=True)
        self.c3.assert_no_ooc()

        assert self.c0.is_blind
        assert not self.c1.is_blind
        assert not self.c2.is_blind
        assert not self.c3.is_blind

        self.c0.assert_received_packet('BN', self.server.config['blackout_background'], over=True)

    def test_02_blindseesnothing(self):
        """
        Situation: C0 and C1 talk to one another. C1 sees normally, C0 nothing.
        """

        self.c0.sic('Hello?')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('Hello?', folder=self.c0_cname,
                                   anim='../../misc/blank', over=True)
        self.c1.assert_received_ic('Hello?', folder=self.c0_cname,
                                   anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c1.sic('Yes I can hear you.')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('Yes I can hear you.', folder=self.c1_cname,
                                   anim='../../misc/blank', over=True)
        self.c1.assert_received_ic('Yes I can hear you.', folder=self.c1_cname,
                                   anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('I cant see you :(')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('I cant see you :(', folder=self.c0_cname,
                                   anim='../../misc/blank', over=True)
        self.c1.assert_received_ic('I cant see you :(', folder=self.c0_cname,
                                   anim='happy', over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c2.sic('I still see myself.')
        self.c2.assert_received_ic('I still see myself.', folder=self.c2_cname,
                                   anim='happy', over=True)
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c3.assert_no_ic()

    def test_03_blindchangesarea(self):
        """
        Situation: C0 changes to C2's area. Still sees nothing.
        """

        self.c0.move_area(4)
        self.convo1()

    def test_04_notblindchangestoarea(self):
        """
        Situation: C1 comes to C0's area and says hi. C0 cannot see C1.
        """

        self.c1.move_area(4)

        self.c1.sic('Hallo mates.')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('Hallo mates.', folder=self.c1_cname,
                                   anim='../../misc/blank', over=True)
        self.c1.assert_received_ic('Hallo mates.', folder=self.c1_cname,
                                   anim='happy', over=True)
        self.c2.assert_received_ic('Hallo mates.', folder=self.c1_cname,
                                   anim='happy', over=True)
        self.c3.assert_no_ic()

        self.c1.sic('Yo.')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('Yo.', folder=self.c1_cname,
                                   anim='../../misc/blank', over=True)
        self.c1.assert_received_ic('Yo.', folder=self.c1_cname,
                                   anim='happy', over=True)
        self.c2.assert_received_ic('Yo.', folder=self.c1_cname,
                                   anim='happy', over=True)
        self.c3.assert_no_ic()

        self.c0.sic('Cant see you either :(.', anim='sad')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c0.assert_received_ic('Cant see you either :(.', folder=self.c0_cname,
                                   anim='../../misc/blank', over=True)
        self.c1.assert_received_ic('Cant see you either :(.', folder=self.c0_cname,
                                   anim='sad', over=True)
        self.c2.assert_received_ic('Cant see you either :(.', folder=self.c0_cname,
                                   anim='sad', over=True)
        self.c3.assert_no_ic()

class TestSenseBlockBlind_03_Advanced(_TestSenseBlockBlind):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.ooc('/blind 0')
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

    def test_01_blindandlights(self):
        """
        Situation:
        1. C2 turns lights off. C0 notices nothing.
        2. C0 leaves room while lights are off and gets no notif of light sttus when they return.
        3. C3 comes to the room and gets notif of lights out
        4. C2 turns lights on. C0 notices nothing, C3 does.

        TODO: Unload this test case as soon as lights test case is up.
        """

        self.c2.ooc('/lights off')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'], over=True)
        self.c0.assert_not_received_ooc('The lights were turned off.')
        self.c1.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c1.assert_received_ooc('{} turned the lights off.'
                                    .format(self.c2_cname), over=True)
        self.c2.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c2.assert_received_ooc('You turned the lights off.', over=True)
        self.c4.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c4.assert_received_ooc('The lights were turned off.', over=True)
        self.convo1()

        self.c0.ooc('/area 5')
        self.c0.discard_all()
        self.c1.assert_received_ooc('You hear footsteps going out of the room.', over=True)
        self.c2.assert_received_ooc('You hear footsteps going out of the room.', over=True)
        self.c4.assert_received_ooc('You hear footsteps going out of the room.', over=True)
        self.c0.ooc('/area 4')
        self.c0.assert_not_received_ooc('You enter a pitch dark room.')
        self.c0.assert_not_received_ooc('You hear footsteps coming into the room.')
        self.c0.discard_all()
        self.c1.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c2.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_received_ooc('You hear footsteps coming into the room.', over=True)

        self.c3.ooc('/area 4')
        self.c0.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c1.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c2.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c3.assert_received_ooc('You enter a pitch dark room.', somewhere=True)
        self.c3.discard_all()
        self.c4.assert_received_ooc('You hear footsteps coming into the room.', over=True)

        self.c2.ooc('/lights on')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'], over=True)
        self.c0.assert_not_received_ooc('The lights were turned on.')
        self.c1.assert_received_packet('BN', self.c0.area.background)
        self.c1.assert_received_ooc('{} turned the lights on.'
                                    .format(self.c2_cname), over=True)
        self.c2.assert_received_packet('BN', self.c0.area.background)
        self.c2.assert_received_ooc('You turned the lights on.', over=True)
        self.c3.assert_received_packet('BN', self.c0.area.background)
        self.c3.assert_received_ooc('The lights were turned on.', over=True)
        self.c4.assert_received_packet('BN', self.c0.area.background)
        self.c4.assert_received_ooc('The lights were turned on.', over=True)
        self.convo1()

    def test_02_blindandautopass(self):
        """
        Situation: C3, with autopass moves to area 5 and then back. C0 only gets footstep notifs.
        """

        self.c3.ooc('/autopass')
        self.c3.move_area(5)
        self.c0.assert_received_ooc('You hear footsteps going out of the room.', over=True)
        self.c2.assert_received_ooc('{} has left to the {}'
                                    .format(self.c3_cname, self.area5.name), over=True)
        self.c1.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()

        self.c3.move_area(4)
        self.c0.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c2.assert_received_ooc('{} has entered from the {}'
                                    .format(self.c3_cname, self.area5.name), over=True)
        self.c1.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()

    def test_03_blindandautopassnolight(self):
        """
        Situation: Autopass and lights off. C0 still only gets footstep notifs.
        """

        self.c3.ooc('/lights off')
        self.c0.assert_received_packet('BN', self.server.config['blackout_background'], over=True)
        self.c0.assert_not_received_ooc('The lights were turned off.')
        self.c2.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c2.assert_received_ooc('{} turned the lights off.'
                                    .format(self.c3_cname), over=True)
        self.c3.assert_received_packet('BN', self.server.config['blackout_background'])
        self.c3.assert_received_ooc('You turned the lights off.', over=True)
        self.c1.discard_all()
        self.c4.discard_all()

        self.c3.move_area(5)
        self.c0.assert_received_ooc('You hear footsteps going out of the room.', over=True)
        self.c2.assert_received_ooc('{} has left to the {}'
                                    .format(self.c3_cname, self.area5.name), over=True)
        self.c4.assert_received_ooc('You hear footsteps going out of the room.', over=True)
        self.c1.discard_all()
        self.c3.discard_all()

        self.c3.move_area(4)
        self.c0.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c2.assert_received_ooc('{} has entered from the {}'
                                    .format(self.c3_cname, self.area5.name), over=True)
        self.c4.assert_received_ooc('You hear footsteps coming into the room.', over=True)
        self.c1.discard_all()
        self.c3.discard_all()