from .test_zonebasic import _TestZone

class TestZoneChangeWatchers_01_Watch(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_watch incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_watch 1000')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_watch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Zone does not exist
        # This was a bug as late as 4.2.0-post2 (it raised an uncaught KeyError)
        self.c1.ooc('/zone_watch zoneThatDoesNotExist')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('`{}` is not a valid zone ID.'.format('zoneThatDoesNotExist'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_newwatcher(self):
        """
        Situation: C1 creates a zone from areas 4 through 6. C2 decides to watch it.
        """

        self.c1.ooc('/zone 4, 6') # Creates zone z0
        self.c1.discard_all()
        self.c2.discard_all() # staff in zone
        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c1}, self.zm.get_zone('z0').get_watchers())

        self.c2.ooc('/zone_watch {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] is now watching your zone.'
                           .format(self.c2_dname, 2), over=True)
        self.c2.assert_ooc('You are now watching zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c2}, self.zm.get_zone('z0').get_watchers())

    def test_03_anothernewwatcher(self):
        """
        Situation: C5 too decides to watch zone z0.
        """

        self.c5.ooc('/zone_watch {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] is now watching your zone.'
                           .format(self.c5_dname, 5), over=True)
        self.c2.assert_ooc('(X) {} [{}] is now watching your zone.'
                           .format(self.c5_dname, 5), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You are now watching zone `{}`.'.format('z0'), over=True)
        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').get_watchers())

    def test_04_differentzonedifferentwatchers(self):
        """
        Situation: C0 (who is made mod) creates a zone z1. C4 (who is made mod) watches their zone.
        """

        self.c0.make_mod(over=False)
        self.c0.discard_all() # Discard all messages related to the zone that might clog next line
        self.c4.make_mod(over=False)
        self.c4.discard_all()
        self.c4.make_mod(over=False)
        self.c0.ooc('/zone {}, {}'.format(1, 3))
        self.c0.discard_all() # Discard notification for logging in while in zone
        self.c1.discard_all() # Discard notification for zone creation
        self.c4.discard_all() # Discard notification for logging in while in zone & zone creation

        self.c4.ooc('/zone_watch {}'.format('z1'))
        self.c0.assert_ooc('(X) {} [{}] is now watching your zone.'
                           .format(self.c4_dname, 4), over=True)
        self.c1.assert_no_packets() # In other zone
        self.c2.assert_no_packets() # In other zone
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You are now watching zone `{}`.'.format('z1'), over=True)
        self.c5.assert_no_packets() # In other zone
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c0, self.c4}, self.zm.get_zone('z1').get_watchers())

    def test_05_nodoublewatching(self):
        """
        Situation: C0 attempts to watch zone z0. C1 attempts to watch z1. Both of them attempt this
        while still watching their original zones. They both fail.
        """

        self.c0.ooc('/zone_watch {}'.format('z0'))
        self.c0.assert_ooc('You cannot watch a zone while watching another.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c0, self.c4}, self.zm.get_zone('z1').get_watchers())

        self.c1.ooc('/zone_watch {}'.format('z1'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You cannot watch a zone while watching another.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c0, self.c4}, self.zm.get_zone('z1').get_watchers())

class TestZoneChangeWatchers_02_Unwatch(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_unwatch incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_watch 1000')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Parameters
        self.c1.ooc('/zone_unwatch 1000')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has no arguments.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_unwatch(self):
        """
        Situation: C1 creates a zone, C2 and C5 start watching it. C2 then unwatches it.
        """

        self.c1.ooc('/zone 4, 6') # Creates zone z0
        self.c2.ooc('/zone_watch {}'.format('z0'))
        self.c5.ooc('/zone_watch {}'.format('z0'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').get_watchers())

        self.c2.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] is no longer watching your zone.'
                           .format(self.c2_dname, 2), over=True)
        self.c2.assert_ooc('You are no longer watching zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] is no longer watching your zone.'
                           .format(self.c2_dname, 2), over=True)
        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c5}, self.zm.get_zone('z0').get_watchers())

    def test_03_cannotunwatchifnotwatching(self):
        """
        Situation: C2, who just unwatched, attempts to unwatch again. This fails. This also fails
        for C4 (who was made mod), who was never watching anything in the first place.
        """

        self.c2.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('You are not watching any zone.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c5}, self.zm.get_zone('z0').get_watchers())

        self.c4.make_mod(over=False)
        self.c4.discard_all() # Discard notification for logging in while in zone

        self.c4.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You are not watching any zone.', over=True)
        self.c5.assert_no_packets()
        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c5}, self.zm.get_zone('z0').get_watchers())

    def test_04_unwatchercancreate(self):
        """
        Situation: C2, who just unwatched a zone, can now freely create a zone.
        """

        self.c2.ooc('/zone 0')
        self.c1.discard_all() # Discard mod notification for zone creation
        self.c2.discard_all()
        self.c4.discard_all() # Discard mod notification for zone creation
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c1, self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c2}, self.zm.get_zone('z1').get_watchers())

    def test_05_creatorunwatches(self):
        """
        Situation: C1, the original creator of the zone, unwatches it. As someone is still watching
        it (C5), the zone survives.
        """

        self.c1.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You are no longer watching zone `{}`.'.format('z0'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] is no longer watching your zone.'
                           .format(self.c1_dname, 1), over=True)
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c2}, self.zm.get_zone('z1').get_watchers())

    def test_06_unwatchercanwatchothers(self):
        """
        Situation: C1, who just unwatched a zone, can now freely watch another zone.
        """

        self.c1.ooc('/zone_watch {}'.format('z1'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z1').get_watchers())

    def test_07_unwatchthenwatch(self):
        """
        Situation: C1 unwatches their watched zone, and can rewatch it in the future again.
        """

        self.c1.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You are no longer watching zone `{}`.'.format('z1'), over=True)
        self.c2.assert_ooc('(X) {} [{}] is no longer watching your zone.'
                           .format(self.c1_dname, 1), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c2}, self.zm.get_zone('z1').get_watchers())

        self.c1.ooc('/zone_watch {}'.format('z1'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z1').get_watchers())

    def test_08_lastpersonunwatches(self):
        """
        Situation: C5 unwatches their zone. As they were the last person watching it, they get a
        special message about their zone being removed. C1/4 also gets a message by being a mod.
        """

        self.c5.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) Zone `{}` was automatically deleted as no one was watching it '
                           'anymore.'.format('z0'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('(X) Zone `{}` was automatically deleted as no one was watching it '
                           'anymore.'.format('z0'), over=True)
        self.c5.assert_ooc('You are no longer watching zone `{}`.'.format('z0'))
        self.c5.assert_ooc('As you were the last person watching it, your zone has been deleted.',
                           over=True)

class TestZoneChangeWatchers_03_Disconnections(_TestZone):
    def test_01_disconnectionmorethanonewatcherremains(self):
        """
        Situation: C1 creates a zone, C2 and C5 watch it. C5 then "disconnects". Server survives as
        normal.
        """

        self.c1.ooc('/zone 4, 6') # Creates zone z0
        self.c2.ooc('/zone_watch {}'.format('z0'))
        self.c5.ooc('/zone_watch {}'.format('z0'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c5.disconnect()
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] disconnected while watching your zone ({}).'
                           .format(self.c5_dname, 5, self.c5.area.id), over=True)
        self.c2.assert_ooc('(X) {} [{}] disconnected while watching your zone ({}).'
                           .format(self.c5_dname, 5, self.c5.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z0').get_watchers())

    def test_02_afterdccancreatemorezones(self):
        """
        Situation: C4 (who is made mod) creates a zone after a player disconnected.
        """

        self.c4.make_mod(over=False)

        self.c4.ooc('/zone 3')
        self.c1.discard_all() # Discard mod notification for zone creation
        self.c4.discard_all()
        self.assertEquals(2, len(self.zm.get_zones()))
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z0').get_watchers())
        self.assertEquals({self.c4}, self.zm.get_zone('z1').get_watchers())

    def test_03_solewatcherdcs(self):
        """
        Situation: C4, the sole watcher of zone z1, disconnects. Zone 1 thus disappears.
        """

        self.c4.disconnect()
        self.c1.assert_ooc('Zone `{}` was automatically deleted as no one was watching it anymore.'
                           .format('z1'))
        self.c1.assert_ooc('(X) {} [{}] disconnected in your zone ({}).'
                           .format(self.c4_dname, 4, self.c4.area.id), over=True)
        self.c2.assert_ooc('(X) {} [{}] disconnected in your zone ({}).'
                           .format(self.c4_dname, 4, self.c4.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.assertEquals(1, len(self.zm.get_zones()))
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z0').get_watchers())

    def test_04_watcherlogsout(self):
        """
        Situation: C2, who is watching Z0, logs out. They stop watching the zone and the other
        watcher, C1, is notified.
        """

        self.c2.make_normie(over=False,
                            other_over=lambda c: c not in self.zm.get_zone('z0').get_watchers())
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] is no longer watching your zone.'
                           .format(self.c2_dname, 2), over=True)
        self.c2.assert_ooc('You are no longer watching zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_05_watcheriscleargmd(self):
        """
        Situation: C2 is made GM again and watches zone z0. C1 then /cleargm's, thus making C2 stop
        watching zone z0. C1 is notified.
        """

        self.c2.make_gm(over=False)
        self.c2.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c2.discard_all()

        self.c1.ooc('/cleargm')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] is no longer watching your zone.'
                           .format(self.c2_dname, 2))
        self.c1.assert_ooc('All GMs logged out.', over=True)
        self.c2.assert_ooc('You are no longer a GM.')
        self.c2.assert_packet('FM', None)
        self.c2.assert_ooc('You are no longer watching zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
