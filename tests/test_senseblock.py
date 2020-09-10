from .structures import _TestSituation4Mc12

class _TestSenseBlock(_TestSituation4Mc12):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(4)

class _UnittestSenseBlock(_TestSenseBlock):
    def test_01_wrongarguments(self):
        """
        Situation: Unauthorized user attempts to sense block, or wrong arguments are passed.
        """

        self.c0.ooc('/{} {}'.format(self.sense, 0))
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{}'.format(self.sense))
        self.c1.assert_ooc('Expected client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} 123'.format(self.sense))
        self.c1.assert_ooc('No targets found.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} aa bb'.format(self.sense))
        self.c1.assert_ooc('`aa bb` does not look like a valid client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_canaffect(self):
        """
        Situation: Authorized user attempts to sense block C0 and succeeds.
        """

        self.c1.ooc('/{} {}'.format(self.sense, 0))
        self.c1.assert_ooc('You have {} {}.'.format(self.sense_pp, self.c0_dname), over=True)
        self.c0.assert_ooc('You have been {}.'.format(self.sense_pp), ooc_over=True)
        self.c2.assert_ooc('(X) {} [{}] has {} {} ({}).'
                           .format(self.c1.displayname, 1, self.sense_pp, self.c0_dname, 0),
                           over=True)
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

        self.sense_affect(self.c0)

    def test_03_canaffectstaff(self):
        """
        Situation: Authorized user attempts to sense block a staff member and succeeds.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 1))
        self.c2.assert_ooc('You have {} {}.'.format(self.sense_pp, self.c1_dname), over=True)
        self.c1.assert_ooc('You have been {}.'.format(self.sense_pp), ooc_over=True)
        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

        self.sense_affect(self.c1)

    def test_04_canaffectself(self):
        """
        Situation: Authorized user attempts to sense block themselves and succeeds.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 2))
        self.c2.assert_ooc('You have {} yourself.'.format(self.sense_pp), ooc_over=True)
        self.c1.assert_ooc('(X) {} [{}] has {} themselves ({}).'
                           .format(self.c2_dname, 2, self.sense_pp, 4),
                           over=True)
        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

        self.sense_affect(self.c2)

    def test_05_unwrongarguments(self):
        """
        Situation: Unauthorized user attempts to sense unblock, or wrong arguments are passed.
        """

        self.c0.ooc('/{} {}'.format(self.sense, 0))
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{}'.format(self.sense))
        self.c1.assert_ooc('Expected client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} 123'.format(self.sense))
        self.c1.assert_ooc('No targets found.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} aa bb'.format(self.sense))
        self.c1.assert_ooc('`aa bb` does not look like a valid client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_06_canunaffect(self):
        """
        Situation: Authorized user attempts to sense unblock C0 and succeeds.
        """

        self.c1.ooc('/{} {}'.format(self.sense, 0))
        self.c1.assert_ooc('You have un{} {}.'.format(self.sense_pp, self.c0_dname), over=True)
        self.c0.assert_ooc('You have been un{}.'.format(self.sense_pp), ooc_over=True)
        self.c2.assert_ooc('(X) {} [{}] has un{} {} ({}).'
                           .format(self.c1.displayname, 1, self.sense_pp, self.c0_dname, 0),
                           over=True)
        self.c3.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

        self.sense_unaffect(self.c0)

    def test_07_canunaffectstaff(self):
        """
        Situation: Authorized user attempts to sense unblock a staff member and succeeds.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 1))
        self.c2.assert_ooc('You have un{} {}.'.format(self.sense_pp, self.c1_dname), over=True)
        self.c1.assert_ooc('You have been un{}.'.format(self.sense_pp), ooc_over=True)
        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

        self.sense_unaffect(self.c1)

    def test_08_canunaffectself(self):
        """
        Situation: Authorized user attempts to sense block themselves and succeeds.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 2))
        self.c2.assert_ooc('You have un{} yourself.'.format(self.sense_pp), ooc_over=True)
        self.c1.assert_ooc('(X) {} [{}] has un{} themselves ({}).'
                           .format(self.c2_dname, 2, self.sense_pp, 4),
                           over=True)

        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

        self.sense_unaffect(self.c2)

    def test_09_affectunaffect(self):
        """
        Situation: Another authorized user attempts to sense block and unblock, and succeeds.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 3))
        self.c2.assert_ooc('You have {} {}.'.format(self.sense_pp, self.c3_dname), over=True)
        self.c3.assert_ooc('You have been {}.'.format(self.sense_pp), ooc_over=True)
        self.c1.assert_ooc('(X) {} [{}] has {} {} ({}).'
                           .format(self.c2.displayname, 2, self.sense_pp, self.c3_dname, 4),
                           over=True)
        self.c0.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert self.sense_attribute(self.c3)

        self.sense_affect(self.c3)

        self.c2.ooc('/{} {}'.format(self.sense, 3))
        self.c2.assert_ooc('You have un{} {}.'.format(self.sense_pp, self.c3_dname), over=True)
        self.c3.assert_ooc('You have been un{}.'.format(self.sense_pp), ooc_over=True)
        self.c1.assert_ooc('(X) {} [{}] has un{} {} ({}).'
                           .format(self.c2.displayname, 2, self.sense_pp, self.c3_dname, 4),
                           over=True)
        self.c0.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

        self.sense_unaffect(self.c3)

    def test_10_persistsonareachange(self):
        """
        Situation: Sense blocked client changes area, and their sense block persists.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 3))
        self.c2.assert_ooc('You have {} {}.'.format(self.sense_pp, self.c3_dname), over=True)
        self.c3.assert_ooc('You have been {}.'.format(self.sense_pp), ooc_over=True)
        self.c1.assert_ooc('(X) {} [{}] has {} {} ({}).'
                           .format(self.c2.displayname, 2, self.sense_pp, self.c3_dname, 4),
                           over=True)
        self.c0.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert self.sense_attribute(self.c3)

        self.sense_affect(self.c3)

        self.c3.move_area(5)
        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert self.sense_attribute(self.c3)

        self.c3.discard_all()

    def test_11_doesntpersistonreconnect(self):
        """
        Situation: Sense blocked client disconnects and on reconnection are no longer sense blocked.
        """
        self.server.disconnect_client(3)
        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)

        self.server.make_clients(1)

        self.c1.assert_no_packets()
        self.c3 = self.server.client_list[3]
        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def sense_affect(self, client):
        pass

    def sense_unaffect(self, client):
        pass
