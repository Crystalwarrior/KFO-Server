from .test_zonebasic import _TestZone

class TestZoneExtraNotifications_01_EnterLeave(_TestZone):
    def test_01_enterzone(self):
        """
        Situation: C1 creates a zone involving areas 3 through 5. C5, who is outside the zone,
        moves in. C1 gets a notification.
        """

        self.c1.ooc('/zone 3, 5')
        self.c1.discard_all()

        self.c4.move_area(4, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) Client {} ({}) has entered your zone ({}).'
                           .format(4, self.c4_dname, 4), over=True)
        self.c2.assert_no_packets() # C2 is not watching zone
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You have entered zone `{}`.'.format('z0'), over=True)
        self.c5.assert_no_packets()

    def test_02_newwatcherenterszone(self):
        """
        Situation: C5 now watches zone and then moves in. C1 gets notification. C5 gets ONE
        notification.
        """

        self.c5.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c5.discard_all()

        self.c5.move_area(3, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) Client {} ({}) has entered your zone ({}).'
                           .format(5, self.c5_dname, 3), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You have entered zone `{}`.'.format('z0'), over=True)

    def test_03_withinzonemovement(self):
        """
        Situation: C5 moves to another area within the zone. No new notifications are sent.
        """

        self.c5.move_area(4, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_04_leavezone(self):
        """
        Situation: C2, in zone z0, moves to an area outside z0. C1 and C5 get notification.
        """

        self.c2.move_area(7, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) Client {} ({}) has left your zone ({}).'
                           .format(2, self.c2_dname, 7), over=True)
        self.c2.assert_ooc('You have left zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) Client {} ({}) has left your zone ({}).'
                           .format(2, self.c2_dname, 7), over=True)

    def test_05_watcherleaveszone(self):
        """
        Situation: C5, who watches z0, moves to an area outside z0. C1 gets notification. C5 gets
        ONE notification.
        """

        self.c5.move_area(7, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) Client {} ({}) has left your zone ({}).'
                           .format(5, self.c5_dname, 7), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You have left zone `{}`.'.format('z0'), over=True)

    def test_06_leavezoneAenterzoneB(self):
        """
        Situation: C5 creates a new zone for their area, where C2 also is. C2 then moves back to
        an area in z0.
        """

        self.c5.ooc('/zone_unwatch')
        self.c5.ooc('/zone')
        self.c1.discard_all()
        self.c5.discard_all()

        self.c2.move_area(5, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) Client {} ({}) has entered your zone ({}).'
                           .format(2, self.c2_dname, 5), over=True)
        self.c2.assert_ooc('You have left zone `z1`.')
        self.c2.assert_ooc('You have entered zone `z0`.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) Client {} ({}) has left your zone ({}).'
                           .format(2, self.c2_dname, 5), over=True)