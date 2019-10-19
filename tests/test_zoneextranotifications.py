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

class TestZoneExtraNotifications_02_ChangeShowname(_TestZone):
    def test_01_manualshownamechange(self):
        """
        Situation: C2 creates a zone involving areas 4 through 5. Then C3 changes their showname
        manually from their "test case situation" one, which was showname3, with /showname.
        C2 gets notified, but not C1 and C5, who are staff not watching the zone, even if C1 is in
        an area part of the zone. C2 is the only staff watching.
        """

        self.c2.ooc('/zone 4, 6')
        self.c1.discard_all()
        self.c2.discard_all()

        o_showname = self.c3.showname
        n_showname = 'newShowname'

        # Changing showname from an existing one to another one
        self.c3.ooc('/showname {}'.format(n_showname))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} changed their showname from `{}` to `{}` in your zone '
                           '({}).'.format(3, o_showname, n_showname, self.c3.area.id), over=True)
        self.c3.assert_ooc('You have set your showname to `{}`.'.format(n_showname), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Removing custom showname altogether
        self.c3.ooc('/showname')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} removed their showname `{}` in your zone ({}).'
                           .format(3, n_showname, self.c3.area.id), over=True)
        self.c3.assert_ooc('You have removed your showname.', over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Setting showname from no custom showname
        self.c3.ooc('/showname {}'.format(n_showname))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} set their showname to `{}` in your zone ({}).'
                           .format(3, n_showname, self.c3.area.id), over=True)
        self.c3.assert_ooc('You have set your showname to `{}`.'.format(n_showname), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_staffshownamechange(self):
        """
        Situation: C1 repeatedly changes C3's showname with /showname_set.
        C2 gets notified and so does C1, but not C5, who is staff not watching the zone.
        """

        o_showname = 'newShowname'
        n_showname = 'betterNewShowname'

        # Changing showname from an existing one to another one
        self.c1.ooc('/showname_set {} {}'.format(3, n_showname))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have set the showname of client {} to `{}`.'
                           .format(3, n_showname), over=True)
        self.c2.assert_ooc('(X) {} changed the showname of client {} from `{}` to `{}` in your '
                           'zone ({}).'
                           .format(self.c1_dname, 3, o_showname, n_showname, self.c3.area.id),
                           over=True)
        self.c3.assert_ooc('Your showname was set to `{}` by a staff member.'
                           .format(n_showname), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Removing custom showname altogether
        self.c1.ooc('/showname_set {}'.format(3))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have removed the showname of client {}.'.format(3), over=True)
        self.c2.assert_ooc('(X) {} removed the showname `{}` of client {} in your zone ({}).'
                           .format(self.c1_dname, n_showname, 3, self.c3.area.id), over=True)
        self.c3.assert_ooc('Your showname was removed by a staff member.', over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Setting showname from no custom showname
        self.c1.ooc('/showname_set {} {}'.format(3, n_showname))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have set the showname of client {} to `{}`.'
                           .format(3, n_showname), over=True)
        self.c2.assert_ooc('(X) {} set the showname of client {} to `{}` in your zone ({}).'
                           .format(self.c1_dname, 3, n_showname, self.c3.area.id), over=True)
        self.c3.assert_ooc('Your showname was set to `{}` by a staff member.'
                           .format(n_showname), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_03_shownameconflict(self):
        """
        Situation: C3 changes their showname to match C0's (whose showname was manually set for the
        test case). C3 then moves to C1's area and has their showname cleared due to conflict.
        This clearing is reported to C2, the sole zone watcher.
        """

        b_showname = 'someShowname'
        self.c0.showname = b_showname
        self.c3.ooc('/showname {}'.format(self.c0.showname))
        self.c2.discard_all()
        self.c3.discard_all()

        self.c3.move_area(self.c0.area.id, discard_trivial=True)
        self.c2.assert_ooc('(X) Client {} had their showname `{}` removed in your zone due to it '
                           'conflicting with the showname of another player in the same area ({}).'
                           .format(3, b_showname, self.c3.area.id), over=True)
        self.c3.assert_ooc('Your showname `{}` was already used in this area, so it has been '
                           'removed.'.format(b_showname), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
