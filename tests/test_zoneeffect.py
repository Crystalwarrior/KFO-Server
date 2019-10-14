from .test_zonebasic import _TestZone

class TestZoneEffect_01_Global(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_global incorrectly.
        """

        # No message
        self.c0.ooc('/zone_global')
        self.c0.assert_ooc('You cannot send an empty message.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_zoneglobal(self):
        """
        Situation: C1 creates a zone where C0, C1, C2, and C3 are. Different players take turns
        sending zone global messages. C4 and C5 never receive them, for they are not in the zone.
        """

        self.c1.ooc('/zone 3, 5')
        self.c1.discard_all()

        self.c0.ooc('/zone_global Hello players.')
        self.c0.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c1.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c2.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c3.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c1.ooc('/zone_global Hello c0.')
        self.c0.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c1.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c2.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c3.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c2.ooc('/zone_global Hello c0!')
        self.c0.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c1.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c2.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c3.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c3.ooc('/zone_global Oi c0.')
        self.c0.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c1.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c2.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c3.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_03_watchercanglobaloutsidezone(self):
        """
        Situation: C5 decides to watch z0. They can now communicate with people inside the zone
        and receive their messages, even if they are not in the zone.
        """

        self.c5.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c3.ooc('/zone_global Oi c5.')
        self.c0.assert_ooc('Oi c5.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c1.assert_ooc('Oi c5.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c2.assert_ooc('Oi c5.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c3.assert_ooc('Oi c5.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_ooc('Oi c5.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)

        self.c5.ooc('/zone_global Hallo')
        self.c0.assert_ooc('Hallo', username='<dollar>ZG[{}][{}]'.format(7, self.c5_dname),
                           over=True)
        self.c1.assert_ooc('Hallo', username='<dollar>ZG[{}][{}]'.format(7, self.c5_dname),
                           over=True)
        self.c2.assert_ooc('Hallo', username='<dollar>ZG[{}][{}]'.format(7, self.c5_dname),
                           over=True)
        self.c3.assert_ooc('Hallo', username='<dollar>ZG[{}][{}]'.format(7, self.c5_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_ooc('Hallo', username='<dollar>ZG[{}][{}]'.format(7, self.c5_dname),
                           over=True)

    def test_04_nowatchingnoglobal(self):
        """
        Situation: C5 unwatches z0. Both C4 and C5 attempt to use /zone_global. This fails.
        """

        self.c5.ooc('/zone_unwatch')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c4.ooc('/zone_global Test')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You are not in a zone.', over=True)
        self.c5.assert_no_packets()

        self.c5.ooc('/zone_global Test')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You are not in a zone.', over=True)

    def test_05_globalwatchingzoneAinzoneB(self):
        """
        Situation: C5 moves to an area in z0. There, they create a different zone involving an area
        with C4 in it. C4 and C5 then use global messages. Only C4 and C5 can see them. Zone global
        messages within z0 are not visible to either.
        """

        self.c5.ooc('/zone 6')
        self.c5.discard_all()
        self.c5.move_area(4)

        self.c5.ooc('/zone_global c4!')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('c4!', username='<dollar>ZG[{}][{}]'.format(4, self.c5_dname),
                           over=True)
        self.c5.assert_ooc('c4!', username='<dollar>ZG[{}][{}]'.format(4, self.c5_dname),
                           over=True)

        self.c4.ooc('/zone_global Yes?')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('Yes?', username='<dollar>ZG[{}][{}]'.format(6, self.c4_dname),
                           over=True)
        self.c5.assert_ooc('Yes?', username='<dollar>ZG[{}][{}]'.format(6, self.c4_dname),
                           over=True)

    def test_06_alias(self):
        """
        Situation: Clients attempt to use /zg, the alias of /zone_global.
        """

        self.c0.ooc('/zg Hello players.')
        self.c0.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c1.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c2.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c3.assert_ooc('Hello players.', username='<dollar>ZG[{}][{}]'.format(4, self.c0_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c1.ooc('/zg Hello c0.')
        self.c0.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c1.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c2.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c3.assert_ooc('Hello c0.', username='<dollar>ZG[{}][{}]'.format(4, self.c1_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c2.ooc('/zg Hello c0!')
        self.c0.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c1.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c2.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c3.assert_ooc('Hello c0!', username='<dollar>ZG[{}][{}]'.format(5, self.c2_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c3.ooc('/zg Oi c0.')
        self.c0.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c1.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c2.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c3.assert_ooc('Oi c0.', username='<dollar>ZG[{}][{}]'.format(5, self.c3_dname),
                           over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

class TestZoneEffect_01_Play(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_play incorrectly.
        """

        # Not staff
        self.c0.ooc('/zone_play e.mp3')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No message
        self.c1.ooc('/zone_play')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You must specify a song.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_play(self):
        """
        Situation: C1 creates a zone involving areas with clients C0, C1, C2 and C3. C1 then plays
        some tracks. Only they are able to listen to it.
        """

        self.c1.ooc('/zone 3, 5')
        self.c1.discard_all()

        self.c1.ooc('/zone_play Hello.mp3')
        self.c0.assert_packet('MC', ('Hello.mp3', 1), over=True)
        self.c1.assert_packet('MC', ('Hello.mp3', 1), over=True)
        self.c2.assert_packet('MC', ('Hello.mp3', 1), over=True)
        self.c3.assert_packet('MC', ('Hello.mp3', 1), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c3.move_area(7)
        self.c5.move_area(5)

        self.c1.ooc('/zone_play Is it you.mp3')
        self.c0.assert_packet('MC', ('Is it you.mp3', 1), over=True)
        self.c1.assert_packet('MC', ('Is it you.mp3', 1), over=True)
        self.c2.assert_packet('MC', ('Is it you.mp3', 1), over=True)
        self.c3.assert_no_packets()
        self.c5.assert_packet('MC', ('Is it you.mp3', 1), over=True)
        self.c4.assert_no_packets()
