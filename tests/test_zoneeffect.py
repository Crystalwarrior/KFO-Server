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
        self.c2.discard_all()

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
        self.c1.discard_all() # Discard mod notification for zone creation and C5 moving into zone

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

class TestZoneEffect_02_Play(_TestZone):
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
        self.c2.discard_all()

        self.c1.ooc('/zone_play BOX 15.mp3')
        self.c0.assert_packet('MC', ('BOX 15.mp3', 1), over=True)
        self.c1.assert_packet('MC', ('BOX 15.mp3', 1))
        self.c1.assert_ooc('You have played track `BOX 15.mp3` in your zone.', over=True)
        self.c2.assert_packet('MC', ('BOX 15.mp3', 1), over=True)
        self.c3.assert_packet('MC', ('BOX 15.mp3', 1), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.c3.move_area(7)
        self.c5.move_area(5)
        self.c1.discard_all() # Discard C3 moving out of zone and C5 moving into zone notifications

        # Check invalid music name warning
        self.c1.ooc('/zone_play Is it you.mp3')
        self.c0.assert_packet('MC', ('Is it you.mp3', 1), over=True)
        self.c1.assert_packet('MC', ('Is it you.mp3', 1))
        self.c1.assert_ooc('You have played track `Is it you.mp3` in your zone.')
        self.c1.assert_ooc('(X) Warning: `Is it you.mp3` is not a recognized track name, so it '
                           'will not loop.', over=True)
        self.c2.assert_packet('MC', ('Is it you.mp3', 1), over=True)
        self.c3.assert_no_packets()
        self.c5.assert_packet('MC', ('Is it you.mp3', 1), over=True)
        self.c4.assert_no_packets()

class TestZoneEffect_03_RPNotifications(_TestZone):
    """
    This class uses /iclock, which has different behavior for the following cases:
        1. The sender
        2. Non-staff and staff who are not watching the zone the area the sender is in belongs to
        3. Staff who are watching the zone that the area the sender is in belongs to

    Assert that the behavior is correct for all cases.
    For consistency, the chat will be set to unlocked at the start of each test for consistent
    output.

    C0 is in Area 4
    C1 is in Area 4 (mod)
    C2 is in Area 5 (gm)
    C3 is in Area 5
    C4 is in Area 6
    C5 is in Area 7 (gm)

    This is the /iclock code for OOC output
    a) client.send_ooc('You {} the IC chat in this area.'.format(status[client.area.ic_lock]))
    b) client.send_ooc_others('The IC chat has been {} in this area.'
                              .format(status[client.area.ic_lock]), is_zstaff_flex=False, in_area=True)
    c&d) client.send_ooc_others('(X) {} has {} the IC chat in area {} ({}).'
                                .format(client.name, status[client.area.ic_lock], client.area.name,
                                        client.area.id), is_zstaff_flex=True)
    """

    def setUp(self):
        super().setUp()
        self.mes_a = 'You locked the IC chat in this area.'
        self.mes_b = 'The IC chat has been locked in this area.'
        self.mes_c = ('(X) {} [{}] has locked the IC chat in area {} ({}).'
                      .format(self.c1_dname, 1, self.c1.area.name, self.c1.area.id))
        self.mes_d = ('(X) {} [{}] has locked the IC chat in area {} ({}).'
                      .format(self.c5_dname, 5, self.c5.area.name, self.c5.area.id))
        self.c1.area.ic_lock = False
        self.c5.area.ic_lock = False

    def test_01_nozone(self):
        """
        Situation: C1 runs /iclock when there are no zones.
        * C0 receives b (non-staff in area)
        * C1 receives a (sender)
        * C2 receives c (staff outside area)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 receives c (staff outside area)
        """

        self.c1.ooc('/iclock')
        self.c0.assert_ooc(self.mes_b, over=True)
        self.c1.assert_ooc(self.mes_a, over=True)
        self.c2.assert_ooc(self.mes_c, over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc(self.mes_c, over=True)

    def test_02_zone(self):
        """
        Situation: C1 creates a zone involving areas 3 through 5. C1 then runs /iclock.
        * C0 receives b (non-staff in area)
        * C1 receives a (sender)
        * C2 does not receive message (staff not in area in zone not watching zone)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 does not receive message (staff not in zone not watching zone)
        """

        self.c1.ooc('/zone 3, 5')
        self.c1.discard_all()
        self.c2.discard_all()

        self.c1.ooc('/iclock')
        self.c0.assert_ooc(self.mes_b, over=True)
        self.c1.assert_ooc(self.mes_a, over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_03_zonewatcherinzone(self):
        """
        Situation: Now C2 starts watching the zone. C1 then runs /iclock.
        * C0 receives b (non-staff in area)
        * C1 receives a (sender)
        * C2 receives c (staff not in area in zone watching zone)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 does not receive message (staff not in zone not watching zone)
        """

        self.c2.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c2.discard_all()

        self.c1.ooc('/iclock')
        self.c0.assert_ooc(self.mes_b, over=True)
        self.c1.assert_ooc(self.mes_a, over=True)
        self.c2.assert_ooc(self.mes_c, over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_03_zonewatchernotinzone(self):
        """
        Situation: Now C5 starts watching the zone. C1 then runs /iclock.
        * C0 receives b (non-staff in area)
        * C1 receives a (sender)
        * C2 receives c (staff not in area in zone watching zone)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 receives c (staff not in zone watching zone)
        """

        self.c5.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c1.ooc('/iclock')
        self.c0.assert_ooc(self.mes_b, over=True)
        self.c1.assert_ooc(self.mes_a, over=True)
        self.c2.assert_ooc(self.mes_c, over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc(self.mes_c, over=True)

    def test_05_zoneindependence(self):
        """
        Situation: C2 logs out and C5 stops watching z0, creates their own zone z1 in area 7 and
        runs /iclock.
        * C0 does not receive message (non-staff outside area)
        * C1 does not receive message (staff outside area outside zone not watching zone)
        * C2 does not receive message (non-staff outside area outside zone watching other zone)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 receives a (sender)

        Then C1 runs /iclock
        * C0 receives b (non-staff in area)
        * C1 receives a (sender)
        * C2 does not receive message (non-staff outside area in zone watching zone)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 does not receive message (staff not in zone not watching zone)
        """

        self.c2.make_normie(over=False,
                            other_over=lambda c: c not in self.zm.get_zone('z0').get_watchers())
        self.c2.discard_all()

        self.c5.ooc('/zone_unwatch')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()
        self.c5.ooc('/zone')
        self.c1.discard_all() # Discard mod notification for zone creation
        self.c5.discard_all()

        self.c5.ooc('/iclock')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc(self.mes_a, over=True)

        self.c1.ooc('/iclock')
        self.c0.assert_ooc(self.mes_b, over=True)
        self.c1.assert_ooc(self.mes_a, over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_06_inzoneAwatchzoneBreceivezoneBnotif(self):
        """
        Situation: C2 is made GM again, unwatches zone z0, then watches z1 while being in an area
        part of z0. Then C5 runs /iclock.
        * C0 does not receive message (non-staff outside area)
        * C1 does not receive message (staff outside area outside zone not watching zone)
        * C2 receives d (staff outside area outside zone watching zone)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 receives a (sender)

        Then C1 runs /iclock.
        * C0 receives b (non-staff in area)
        * C1 receives a (sender)
        * C2 does not receive message (non-staff outside area in zone watching other zone)
        * C3 does not receive message (non-staff outside area)
        * C4 does not receive message (non-staff outside area)
        * C5 does not receive message (staff not in zone not watching zone)
        """

        self.c2.make_gm(over=False)
        self.c2.ooc('/zone_unwatch')
        self.c2.ooc('/zone_watch z1')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c5.ooc('/iclock')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc(self.mes_d, over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc(self.mes_a, over=True)

        self.c1.ooc('/iclock')
        self.c0.assert_ooc(self.mes_b, over=True)
        self.c1.assert_ooc(self.mes_a, over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
