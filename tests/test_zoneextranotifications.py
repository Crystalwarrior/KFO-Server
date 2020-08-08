from .test_zonebasic import _TestZone

class TestZoneExtraNotifications_01_EnterLeave(_TestZone):
    def test_01_enterzone(self):
        """
        Situation: C1 creates a zone involving areas 3 through 5. C5, who is outside the zone,
        moves in. C1 gets a notification.
        """

        self.c1.ooc('/zone 3, 5')
        self.c1.discard_all()
        self.c2.discard_all()

        self.c4.move_area(4, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has entered your zone ({}->{}).'
                           .format(self.c4_dname, 4, 6, 4), over=True)
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
        self.c1.assert_ooc('(X) {} [{}] has entered your zone ({}->{}).'
                           .format(self.c5_dname, 5, 7, 3), over=True)
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
        self.c1.assert_ooc('(X) {} [{}] has left your zone ({}->{}).'
                           .format(self.c2_dname, 2, 5, 7), over=True)
        self.c2.assert_ooc('You have left zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has left your zone ({}->{}).'
                           .format(self.c2_dname, 2, 5, 7), over=True)

    def test_05_watcherleaveszone(self):
        """
        Situation: C5, who watches z0, moves to an area outside z0. C1 gets notification. C5 gets
        ONE notification.
        """

        self.c5.move_area(7, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has left your zone ({}->{}).'
                           .format(self.c5_dname, 5, 4, 7), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) You have left zone `{}`. To stop receiving its notifications, stop '
                           'watching it with /zone_unwatch'.format('z0'), over=True)

    def test_06_leavezoneAenterzoneB(self):
        """
        Situation: C5 creates a new zone for their area, where C2 also is. C2 then moves back to
        an area in z0.
        """

        self.c5.ooc('/zone_unwatch')
        self.c5.ooc('/zone')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c2.move_area(5, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has entered your zone ({}->{}).'
                           .format(self.c2_dname, 2, 7, 5), over=True)
        self.c2.assert_ooc('You have left zone `z1`.')
        self.c2.assert_ooc('(X) You have entered zone `z0`. To be able to receive its '
                           'notifications, start watching it with /zone_watch z0', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has left your zone ({}->{}).'
                           .format(self.c2_dname, 2, 7, 5), over=True)

    def test_07_multiclientsenterzone(self):
        """
        Situation: C0, C1 and C2 are made multiclients of one another manually. They all move to
        C5's zone in order. C5 is given the multiclienting warning for C1 and C2.
        """

        self.c1.ipid = 0
        self.c2.hdid = '0'

        self.c0.move_area(7, discard_trivial=True)
        self.c0.assert_ooc('You have left zone `z0`.')
        self.c0.assert_ooc('You have entered zone `z1`.', over=True)
        self.c1.assert_ooc('(X) {} [{}] has left your zone ({}->{}).'
                           .format(self.c0_dname, 0, 4, 7), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has entered your zone ({}->{}).'
                           .format(self.c0_dname, 0, 4, 7), over=True)

        # One multiclient
        self.c1.move_area(7, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) You have left zone `z0`. To stop receiving its notifications, stop '
                           'watching it with /zone_unwatch')
        self.c1.assert_ooc('(X) You have entered zone `z1`. To be able to receive its '
                           'notifications, start watching it with /zone_watch z1', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has entered your zone ({}->{}).'
                           .format(self.c1_dname, 1, 4, 7))
        self.c5.assert_ooc('(X) Warning: Client {} is multiclienting in your zone. Do '
                           '/multiclients {} to take a look.'.format(1, 1), over=True)

        # >1 multiclient
        self.c2.move_area(7, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has left your zone ({}->{}).'
                           .format(self.c2_dname, 2, 5, 7), over=True)
        self.c2.assert_ooc('You have left zone `z0`.')
        self.c2.assert_ooc('(X) You have entered zone `z1`. To be able to receive its '
                           'notifications, start watching it with /zone_watch z1', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has entered your zone ({}->{}).'
                           .format(self.c2_dname, 2, 5, 7))
        self.c5.assert_ooc('(X) Warning: Client {} is multiclienting in your zone. Do '
                           '/multiclients {} to take a look.'.format(2, 2), over=True)

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
        self.c2.assert_ooc('(X) {} [{}] changed the showname of client {} from `{}` to `{}` in '
                           'your zone ({}).'
                           .format(self.c1_dname, 1, 3, o_showname, n_showname, self.c3.area.id),
                           over=True)
        self.c3.assert_ooc('Your showname was set to `{}` by a staff member.'
                           .format(n_showname), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Removing custom showname altogether
        self.c1.ooc('/showname_set {}'.format(3))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have removed the showname of client {}.'.format(3), over=True)
        self.c2.assert_ooc('(X) {} [{}] removed the showname `{}` of client {} in your zone ({}).'
                           .format(self.c1_dname, 1, n_showname, 3, self.c3.area.id), over=True)
        self.c3.assert_ooc('Your showname was removed by a staff member.', over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Setting showname from no custom showname
        self.c1.ooc('/showname_set {} {}'.format(3, n_showname))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have set the showname of client {} to `{}`.'
                           .format(3, n_showname), over=True)
        self.c2.assert_ooc('(X) {} [{}] set the showname of client {} to `{}` in your zone ({}).'
                           .format(self.c1_dname, 1, 3, n_showname, self.c3.area.id), over=True)
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

class TestZoneExtraNotifications_03_ChangeCharacter(_TestZone):
    """
    A character can be changed by
    1. Client using the character select screeen with a "CC" packet
    2. Client changed to an area and their character was used
    3. Client changed to an area and their character was restricted
    4. Staff set a character to restricted, and automatically has clients in area using them restrc
    5. Staff logs out while using restricted character
    6. Client changes character with /randomchar
    7. Client changes character with /switch
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sc0_name = cls.server.char_list[0]
        cls.sc1_name = cls.server.char_list[1]
        cls.sc2_name = cls.server.char_list[2]
        cls.sc3_name = cls.server.char_list[3]
        cls.scs_name = cls.server.config['spectator_name']
        cls.expected_next_results = None

        class x():
            def __init__(self, expected_next_results=None):
                cls.expected_next_results = expected_next_results

            @staticmethod
            def choice(seq):
                if not cls.expected_next_results:
                    raise KeyError('No expected results left for custom random object.')
                to_return = cls.expected_next_results.pop(0)
                if to_return not in seq:
                    raise ValueError('Expected next random choice {} is not among actual choices {}'
                                     .format(to_return, seq))
                return to_return

        cls.random_factory = x

    def test_01_fromcharselect(self):
        """
        Situation: C2 creates a zone involving areas 4 through 5. C0 in the zone changes character.
        Only C2 is notified, as the only zone watcher.
         Current chars
        C0: 3   C1: 1   C2: 2   C3: 3   C4: -1  C5: -1
        """

        self.c2.ooc('/zone 4, 6')
        self.c1.discard_all()
        self.c2.discard_all()

        self.c0.send_command_cts("CC#0#3#FAKEHDID#%") # Attempt to pick char 3
        self.c0.assert_packet('PV', (0, 'CID', 3), over=True)
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} has changed from character `{}` to `{}` in your zone '
                           '({}).'.format(0, self.sc0_name, self.sc3_name, self.c0.area.id),
                           over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_fromcharconflict(self):
        """
        Situation: C3 moves to C0's area, where they encounter a character conflict, C0 is using
        C3's character! C3 is randomly (read: forced by test) changed to char 2,
        C2 gets notified of the switch.
         Current chars
        C0: 3   C1: 2   C2: 2   C3: 3   C4: -1  C5: -1
        """

        self.server.random = self.random_factory(expected_next_results=[2]) # Force random to be 2

        self.c3.move_area(self.c0.area.id, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} had their character changed from `{}` to `{}` in your '
                           'zone as their old character was taken in their new area ({}).'
                           .format(3, self.sc3_name, self.sc2_name, self.c0.area.id), over=True)
        self.c3.assert_packet('PV', (3, 'CID', 2))
        self.c3.assert_ooc('Your character was taken in your new area, switched to `{}`.'
                           .format(self.sc2_name), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_03_frompreviouscharrestricted(self):
        """
        Situation: Area 6 is set to restrict character 2, C3's char, manually. C3 then moves there
        and is randomly changed to char 0. C2 gets notified of the switch.
         Current chars
        C0: 3   C1: 2   C2: 2   C3: 3   C4: -1  C5: -1
        """

        self.server.random = self.random_factory(expected_next_results=[0]) # Force random to be 0
        self.area6.restricted_chars = {self.sc2_name}

        self.c3.move_area(6, discard_trivial=True)
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} had their character changed from `{}` to `{}` in your '
                           'zone as their old character was restricted in their new area ({}).'
                           .format(3, self.sc2_name, self.sc0_name, self.c3.area.id), over=True)
        self.c3.assert_packet('PV', (3, 'CID', 0))
        self.c3.assert_ooc('Your character was restricted in your new area, switched to `{}`.'
                           .format(self.sc0_name), over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_04_fromnewcharrestricted(self):
        """
        Situation: C1 moves to area 6 and restricts character 0, C3's char. C2 has their char
        randomly changed to char 3 (the only available one). C2 gets notified of the switch.
         Current chars
        C0: 3   C1: 1   C2: 2   C3: 3   C4: -1  C5: -1
        """

        self.server.random = self.random_factory(expected_next_results=[3])
        self.c1.move_area(6)

        self.c1.ooc('/char_restrict {}'.format(self.sc0_name))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have disabled the use of character `{}` in this area.'
                           .format(self.sc0_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] has disabled the use of character `{}` in area {} ({}).'
                           .format(self.c1.displayname, 1, self.sc0_name, self.c1.area.name,
                                   self.c1.area.id))
        self.c2.assert_ooc('(X) Client {} had their character changed from `{}` to `{}` in your '
                           'zone as their old character was just restricted in their new area ({}).'
                           .format(self.c3.id, self.sc0_name, self.sc3_name, self.c3.area.id),
                           over=True)
        self.c3.assert_ooc('A staff member has disabled the use of character {} in this area.'
                           .format(self.sc0_name))
        self.c3.assert_packet('PV', (3, 'CID', 3))
        self.c3.assert_ooc('Your character has been set to restricted in this area by a staff '
                           'member. Switching you to `{}`.'.format(self.sc3_name), over=True)
        self.c4.assert_ooc('A staff member has disabled the use of character {} in this area.'
                           .format(self.sc0_name), over=True)
        self.c5.assert_no_packets()

    def test_05_fromstafflogoutusingrestricted(self):
        """
        Situation: C1 switches to char 0, which they have just restricted. C1 then logs out, and is
        randomly changed to char 1 (their former one and currently only available one). C2 gets
        notified of the switch.
         Current chars
        C0: 3   C1: 1   C2: 2   C3: 3   C4: -1  C5: -1
        """

        self.server.random = self.random_factory(expected_next_results=[1])
        self.c1.send_command_cts("CC#1#0#FAKEHDID#%") # Attempt to pick char 0
        self.c1.assert_packet('PV', (1, 'CID', 0), over=True)
        self.c2.discard_all()

        self.c1.make_normie(over=False)
        self.c0.assert_no_packets()
        self.c1.assert_packet('PV', (1, 'CID', 1))
        self.c1.assert_ooc('Your character has been set to restricted in this area by a staff '
                           'member. Switching you to `{}`.'.format(self.sc1_name), over=True)
        self.c2.assert_ooc('(X) Client {} had their character changed from `{}` to `{}` in your '
                           'zone as their old character was restricted in their area ({}).'
                           .format(self.c1.id, self.sc0_name, self.sc1_name, self.c1.area.id),
                           over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_06_fromrandomchar(self):
        """
        Situation: Area 6's restricted chars are manually blanked out. C4 does /randomchar and gets
        randomly changed to char 0. C2 gets notified of the switch.
         Current chars
        C0: 3   C1: 1   C2: 2   C3: 3   C4: 0  C5: -1
        """

        self.area6.restricted_chars = set()
        self.server.random = self.random_factory(expected_next_results=[0])

        self.c4.ooc('/randomchar')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} has changed from character `{}` to `{}` in your zone '
                           '({}).'.format(4, self.scs_name, self.sc0_name, self.c4.area.id),
                           over=True)
        self.c3.assert_no_packets()
        self.c4.assert_packet('PV', (4, 'CID', 0))
        self.c4.assert_ooc('Randomly switched to `{}`.'.format(self.sc0_name), over=True)
        self.c5.assert_no_packets()

    def test_07_fromswitch(self):
        """
        Situation: C4 switches to char 2 with /switch. C2 gets notified of the switch.
         Current chars
        C0: 3   C1: 1   C2: 2   C3: 3   C4: 2  C5: -1
        """

        self.c4.ooc('/switch {}'.format(self.sc2_name))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) Client {} has changed from character `{}` to `{}` in your zone '
                           '({}).'.format(4, self.sc0_name, self.sc2_name, self.c4.area.id),
                           over=True)
        self.c3.assert_no_packets()
        self.c4.assert_packet('PV', (4, 'CID', 2))
        self.c4.assert_ooc('Character changed.', over=True)
        self.c5.assert_no_packets()

class TestZoneExtraNotifications_04_Disconnection(_TestZone):
    def test_01_nonstaffleaves(self):
        """
        Situation: C2 creates a zone involving areas 4 through 6. C5 decides to watch zone, but not
        C1. C4, non-staff in zone, leaves. C1 and C5 get notified, not C2.
        """

        self.c2.ooc('/zone 4, 6')
        self.c5.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c4.disconnect()
        self.c0.assert_no_packets()
        self.c1.assert_no_packets() # Not watching zone
        self.c2.assert_ooc('(X) {} [{}] disconnected in your zone ({}).'
                           .format(self.c4_dname, 4, self.c4.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] disconnected in your zone ({}).'
                           .format(self.c4_dname, 4, self.c4.area.id), over=True)

    def test_02_staffwatcherleaves(self):
        """
        Situation: C2, a staff zone watcher, leaves. Only C5 gets notified.
        """

        self.c2.disconnect()
        self.c0.assert_no_packets()
        self.c1.assert_no_packets() # Not watching zone
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        # self.c4.assert_no_packets() # NO c4
        self.c5.assert_ooc('(X) {} [{}] disconnected while watching your zone ({}).'
                           .format(self.c2_dname, 2, self.c2.area.id), over=True)

    def test_03_staffnonwatcherleaves(self):
        """
        Situation: C1, a staff non-zone watcher, leaves. Only C5 gets notified
        """

        self.c1.disconnect()
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        # self.c2.assert_no_packets() # NO c2
        self.c3.assert_no_packets()
        # self.c4.assert_no_packets() # NO c4
        self.c5.assert_ooc('(X) {} [{}] disconnected in your zone ({}).'
                           .format(self.c1_dname, 1, self.c1.area.id), over=True)

    def test_04_outofzoneleaves(self):
        """
        Situation: C3 goes out of zone and then disconnects. C5 gets no notification of DC (they do
        of them leaving the zone, but that is not tested here).
        """

        self.c3.move_area(0)
        self.c5.discard_all()

        self.c3.disconnect()
        self.c0.assert_no_packets()
        # self.c1.assert_no_packets() # NO c1
        # self.c2.assert_no_packets() # NO c2
        self.c3.assert_no_packets()
        # self.c4.assert_no_packets() # NO c4
        self.c5.assert_no_packets()