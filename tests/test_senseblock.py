from .structures import _TestSituation4Mc12

class _UnittestSenseBlock(_TestSituation4Mc12):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(4)
        cls.c0_charname = cls.c0.get_char_name() #'Kaede Akamatsu_HD'
        cls.c1_charname = cls.c1.get_char_name() #'Shuichi Saihara_HD'
        cls.c2_charname = cls.c2.get_char_name() #'Maki Harukawa_HD'
        cls.c3_charname = cls.c3.get_char_name() #'Monokuma_HD'

    def test_01_wrongarguments(self):
        """
        Situation: Unauthorized user attempts to sense block, or wrong arguments are passed.
        """

        self.c0.ooc('/{} {}'.format(self.sense, 0))
        self.c0.assert_received_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{}'.format(self.sense))
        self.c1.assert_received_ooc('Expected client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} 123'.format(self.sense))
        self.c1.assert_received_ooc('No targets found.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} aa bb'.format(self.sense))
        self.c1.assert_received_ooc('This command has 1 argument.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_canaffect(self):
        """
        Situation: Authorized user attempts to sense block C0 and succeeds.
        """

        self.c1.ooc('/{} {}'.format(self.sense, 0))
        self.c1.assert_received_ooc('You have {} {}.'.format(self.sense_pp, self.c0_charname),
                                    over=True)
        self.c0.assert_received_ooc('You have been {}.'.format(self.sense_pp), over=True)
        self.c2.assert_received_ooc('{} has {} {} ({}).'
                                    .format(self.c1.name, self.sense_pp, self.c0_charname, 0),
                                    over=True)
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_04_canaffectstaff(self):
        """
        Situation: Authorized user attempts to sense block a staff member and succeeds.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 1))
        self.c2.assert_received_ooc('You have {} {}.'.format(self.sense_pp, self.c1_charname),
                                    over=True)
        self.c1.assert_received_ooc('You have been {}.'.format(self.sense_pp), over=True)
        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_05_canaffectself(self):
        """
        Situation: Authorized user attempts to sense block themselves and succeeds.
        TODO: Figure out repetition.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 2))
        self.c2.assert_received_ooc('You have {} {}.'.format(self.sense_pp, self.c2_charname))
        self.c2.assert_received_ooc('You have been {}.'.format(self.sense_pp), over=True)
        self.c1.assert_received_ooc('{} has {} {} ({}).'
                                    .format(self.c2.name, self.sense_pp, self.c2_charname, 4),
                                    over=True)

        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_06_unwrongarguments(self):
        """
        Situation: Unauthorized user attempts to sense unblock, or wrong arguments are passed.
        """

        self.c0.ooc('/{} {}'.format(self.sense, 0))
        self.c0.assert_received_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{}'.format(self.sense))
        self.c1.assert_received_ooc('Expected client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} 123'.format(self.sense))
        self.c1.assert_received_ooc('No targets found.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/{} aa bb'.format(self.sense))
        self.c1.assert_received_ooc('This command has 1 argument.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_07_canunaffect(self):
        """
        Situation: Authorized user attempts to sense unblock C0 and succeeds.
        """

        self.c1.ooc('/{} {}'.format(self.sense, 0))
        self.c1.assert_received_ooc('You have un{} {}.'.format(self.sense_pp, self.c0_charname),
                                    over=True)
        self.c0.assert_received_ooc('You have been un{}.'.format(self.sense_pp), over=True)
        self.c2.assert_received_ooc('{} has un{} {} ({}).'
                                    .format(self.c1.name, self.sense_pp, self.c0_charname, 0),
                                    over=True)
        self.c3.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_09_canunaffectstaff(self):
        """
        Situation: Authorized user attempts to sense unblock a staff member and succeeds.
        TODO: Figure out repetition.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 1))
        self.c2.assert_received_ooc('You have un{} {}.'.format(self.sense_pp, self.c1_charname),
                                    over=True)
        self.c1.assert_received_ooc('You have been un{}.'.format(self.sense_pp), over=True)
        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_10_canunaffectself(self):
        """
        Situation: Authorized user attempts to sense block themselves and succeeds.
        TODO: Figure out repetition.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 2))
        self.c2.assert_received_ooc('You have un{} {}.'.format(self.sense_pp, self.c2_charname))
        self.c2.assert_received_ooc('You have been un{}.'.format(self.sense_pp), over=True)
        self.c1.assert_received_ooc('{} has un{} {} ({}).'
                                    .format(self.c2.name, self.sense_pp, self.c2_charname, 4),
                                    over=True)

        self.c0.assert_no_ooc()
        self.c3.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_11_affectunaffect(self):
        """
        Situation: Another authorized user attempts to sense block and unblock, and succeeds.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 3))
        self.c2.assert_received_ooc('You have {} {}.'.format(self.sense_pp, self.c3_charname),
                                    over=True)
        self.c3.assert_received_ooc('You have been {}.'.format(self.sense_pp), over=True)
        self.c1.assert_received_ooc('{} has {} {} ({}).'
                                    .format(self.c2.name, self.sense_pp, self.c3_charname, 4),
                                    over=True)
        self.c0.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert self.sense_attribute(self.c3)

        self.c2.ooc('/{} {}'.format(self.sense, 3))
        self.c2.assert_received_ooc('You have un{} {}.'.format(self.sense_pp, self.c3_charname),
                                    over=True)
        self.c3.assert_received_ooc('You have been un{}.'.format(self.sense_pp), over=True)
        self.c1.assert_received_ooc('{} has un{} {} ({}).'
                                    .format(self.c2.name, self.sense_pp, self.c3_charname, 4),
                                    over=True)
        self.c0.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

    def test_12_persistsonareachange(self):
        """
        Situation: Sense blocked client changes area, and their sense block persists.
        """

        self.c2.ooc('/{} {}'.format(self.sense, 3))
        self.c2.assert_received_ooc('You have {} {}.'.format(self.sense_pp, self.c3_charname),
                                    over=True)
        self.c3.assert_received_ooc('You have been {}.'.format(self.sense_pp), over=True)
        self.c1.assert_received_ooc('{} has {} {} ({}).'
                                    .format(self.c2.name, self.sense_pp, self.c3_charname, 4),
                                    over=True)
        self.c0.assert_no_ooc()

        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert self.sense_attribute(self.c3)

        self.c3.move_area(5)
        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert self.sense_attribute(self.c3)

        self.c3.discard_all()

    def test_13_doesntpersistonreconnect(self):
        """
        Situation: Sense blocked client disconnects and on reconnection are no longer sense blocked.
        """

        self.server.disconnect_client(3)
        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)

        self.server.make_clients(1)
        self.c3 = self.server.client_list[3]
        assert not self.sense_attribute(self.c0)
        assert not self.sense_attribute(self.c1)
        assert not self.sense_attribute(self.c2)
        assert not self.sense_attribute(self.c3)

class TestSenseBlock_01_BlindBasic(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'blind'
        cls.sense_pp = 'blinded'
        cls.sense_attribute = lambda x, c: c.is_blind

class TestSenseBlock_02_DeafBasic(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'deafen'
        cls.sense_pp = 'deafened'
        cls.sense_attribute = lambda x, c: c.is_deaf

class TestSenseBlock_03_GagBasic(_UnittestSenseBlock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sense = 'gag'
        cls.sense_pp = 'gagged'
        cls.sense_attribute = lambda x, c: c.is_gagged
