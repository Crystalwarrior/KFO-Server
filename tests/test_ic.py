from .structures import _TestSituation5Mc1Gc2


class _TestIC(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(5)
        cls.c4.move_area(4)


class TestIC_01_Basic(_TestIC):
    def test_01_areaencapsulation(self):
        """
        Situation: Clients try to send messages
        """

        self.c1.sic('Hello world.')
        self.c0.assert_ic('Hello world.', folder=self.c1_cname, over=True)
        self.c1.assert_ic('Hello world.', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_no_ic()

        self.c0.sic('Hello you.')
        self.c0.assert_ic('Hello you.', folder=self.c0_cname, over=True)
        self.c1.assert_ic('Hello you.', folder=self.c0_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_no_ic()

        self.c3.sic('Hello world.')
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_no_ic()
        self.c3.assert_ic('Hello world.', folder=self.c3_cname, over=True)
        self.c4.assert_no_ic()

    def test_02_movetoarea(self):
        """
        Situation: C3 moves to C0's area and says hi in IC.
        """

        self.c3.move_area(0)

        self.c3.sic('Hi there')
        self.c0.assert_ic('Hi there', folder=self.c3_cname, over=True)
        self.c1.assert_ic('Hi there', folder=self.c3_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_ic('Hi there', folder=self.c3_cname, over=True)
        self.c4.assert_no_ic()

    def test_03_justoneinarea(self):
        """
        Situation: C3 moves to an empty area and only they receive their IC messae.
        """

        self.c3.move_area(7)

        self.c3.sic('Anyone in here?')
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_no_ic()
        self.c3.assert_ic('Anyone in here?', folder=self.c3_cname, over=True)
        self.c4.assert_no_ic()

    def test_04_repeatedmessages(self):
        """
        Situation: C2 attempts to send the exact same message with the same character. The server
        filters it out, so they do not receive the MS packet and they don't show the message in IC.
        """

        self.c3.sic('Anyone in here?')
        self.c3.assert_no_packets()


class TestIC_02_GlobalIC(_TestIC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients try to use /globalic incorectly.
        """

        # Not staff
        self.c0.ooc('/globalic 3, 5')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c0.multi_ic)

        # Non-existant area
        self.c2.ooc('/globalic 100')  # No area called 100, or with ID 100 in test scenario
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area `100`.', over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c2.multi_ic)

        self.c2.ooc('/globalic {}, 101'.format(self.a0_name))
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area `101`.', over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c2.multi_ic)

        # Not using commas to separate
        self.c2.ooc('/globalic {} {}'.format(2, 5))
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area `2 5`.', over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c2.multi_ic)

        # Not using ,\ for areas with , in their names (self.a2_name = "Class Trial Room,\ 2")
        self.c2.ooc('/globalic {}, {}'.format(self.a2_name, self.a7_name))
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('This command has from 1 to 2 arguments.', over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c2.multi_ic)

        self.c2.ooc('/globalic {}'.format(self.a2_name))
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area `Class Trial Room`.', over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c2.multi_ic)

        # End area < Start area
        self.c2.ooc('/globalic {}, {}'.format(5, 2))
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('The ID of the first area must be lower than the ID of the second area.',
                           over=True)
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c2.multi_ic)

    def test_02_icinrangeonly(self):
        """
        Situation: C1 activates global IC in areas 1 through 4. C1, C2, C4 receive the message.
        C2 attempts to respond, but only C2 and C4 (in C2's area) get the IC message.
        """

        self.c1.move_area(1)
        self.c3.move_area(7)

        # C0 in A0
        # C1 in A1
        # C2 in A4
        # C3 in A7
        # C4 in A4

        self.c1.ooc('/globalic {}, {}'.format(1, 5))
        self.c1.assert_ooc('Your IC messages will now be sent to areas {} through {}.'
                           .format(self.a1_name, self.a5_name))
        self.c1.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)
        self.assertEqual(self.c1.multi_ic, [self.area1, self.area5])

        self.c1.sic('Hallo mates.')
        self.c1.assert_ooc('Sent global IC message "Hallo mates." to areas {} through {}.'
                           .format(self.a1_name, self.a5_name), ooc_over=True)
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)
        self.c2.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)
        self.c3.assert_no_ic()
        self.c4.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)

        self.c2.sic('Hallo mate.')
        self.c4.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_ic('Hallo mate.', folder=self.c2_cname, over=True)
        self.c3.assert_no_ic()
        self.c4.assert_ic('Hallo mate.', folder=self.c2_cname, over=True)

    def test_03_moveinoutrange(self):
        """
        Situation: C4 moves out of C1's global IC range. C3 moves in range.
        C1 talks IC. C1, C2, C3 receive it.
        """

        self.c4.move_area(0)
        self.c3.move_area(5)

        self.c1.sic('Hallo new mates.')
        self.c1.assert_ooc('Sent global IC message "Hallo new mates." to areas {} through {}.'
                           .format(self.a1_name, self.a5_name), ooc_over=True)
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hallo new mates.', folder=self.c1_cname, over=True)
        self.c2.assert_ic('Hallo new mates.', folder=self.c1_cname, over=True)
        self.c3.assert_ic('Hallo new mates.', folder=self.c1_cname, over=True)
        self.c4.assert_no_ic()

    def test_04_senderoutofrange(self):
        """
        Situation: C1 makes a new range in which they are not a part of.
        When they send IC messages, they do not receive them.
        """

        self.c1.ooc('/globalic {}, {}'.format(4, 5))
        self.c1.assert_ooc('Your IC messages will now be sent to areas {} through {}.'
                           .format(self.a4_name, self.a5_name))
        self.c1.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)
        self.assertEqual(self.c1.multi_ic, [self.area4, self.area5])

        self.c1.sic('Hello players.')
        self.c1.assert_ooc('Sent global IC message "Hello players." to areas {} through {}.'
                           .format(self.a4_name, self.a5_name), over=True)
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_ic('Hello players.', folder=self.c1_cname, over=True)
        self.c3.assert_ic('Hello players.', folder=self.c1_cname, over=True)
        self.c4.assert_no_ic()

    def test_05_unwrongarguments(self):
        """
        Situation: Clients attempt to use /unglobalic incorrectly.
        """

        # Not staff
        self.c0.ooc('/unglobalic')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertIsNone(self.c0.multi_ic)

        # Pass arguments
        self.c1.ooc('/unglobalic Test')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('This command has no arguments.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertEqual(self.c1.multi_ic, [self.area4, self.area5])  # Still has it from prev test

    def test_06_disableglobalic(self):
        """
        Situation: C1 disables global IC. Then they send an IC message.
        Only C1 receives it (only person in area).
        """

        self.c1.ooc('/unglobalic')
        self.c1.assert_ooc('Your IC messages will now be only sent to your current area.',
                           over=True)
        self.assertIsNone(self.c1.multi_ic)

        self.c1.sic('Hello?')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hello?', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_no_ic()


class TestIC_03_GlobalIC_Pre(_TestIC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients try to use /globalic incorectly.
        """

        # Not staff
        self.c0.ooc('/globalic_pre >>>')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.c4.assert_no_ooc()
        self.assertEqual(self.c0.multi_ic_pre, '')

    def test_02_multipletimes(self):
        """
        Situation: Same client uses globalic_pre multiple times.
        """

        self.c1.ooc('/globalic {}, {}'.format(0, 3))
        self.c1.assert_ooc('Your IC messages will now be sent to areas {} through {}.'
                           .format(self.a0_name, self.a3_name))
        self.c1.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)
        self.assertEqual(self.c1.multi_ic_pre, '')

        self.c1.ooc('/globalic_pre *')
        self.c1.assert_ooc('You have set your global IC prefix to *', over=True)
        self.assertEqual(self.c1.multi_ic_pre, '*')

        self.c1.ooc('/globalic_pre **')
        self.c1.assert_ooc('You have set your global IC prefix to **', over=True)
        self.assertEqual(self.c1.multi_ic_pre, '**')

        self.c1.ooc('/globalic_pre *')
        self.c1.assert_ooc('You have set your global IC prefix to *', over=True)
        self.assertEqual(self.c1.multi_ic_pre, '*')

        self.c1.ooc('/globalic_pre *')
        self.c1.assert_ooc('You have set your global IC prefix to *', over=True)
        self.assertEqual(self.c1.multi_ic_pre, '*')

        self.c1.ooc('/globalic_pre')
        self.c1.assert_ooc('You have removed your global IC prefix.', over=True)
        self.assertEqual(self.c1.multi_ic_pre, '')

    def test_03_icinrangeonly(self):
        """
        Situation: C1 activates global IC in areas 1 through 4 and sets their global IC prefix
        to ">>>". Then, they send two messages:
        * ">>>Hallo mates": C1, C2, C4 receive the message "Hallo mates" (prefix filtered out)
        * "Hallo there": Only C1 receives (only person in area)
        C2 attempts to respond, but only C2 and C4 (in C2's area) get the IC message.
        """

        self.c1.move_area(1)
        self.c3.move_area(7)

        # C0 in A0
        # C1 in A1
        # C2 in A4
        # C3 in A7
        # C4 in A4

        self.c1.ooc('/globalic {}, {}'.format(1, 5))
        self.c1.assert_ooc('Your IC messages will now be sent to areas {} through {}.'
                           .format(self.a1_name, self.a5_name))
        self.c1.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)
        self.c1.ooc('/globalic_pre {}'.format('>>>'))
        self.c1.assert_ooc('You have set your global IC prefix to >>>', over=True)

        self.c1.sic('>>>Hallo mates.')
        self.c1.assert_ooc('Sent global IC message "Hallo mates." to areas {} through {}.'
                           .format(self.a1_name, self.a5_name), ooc_over=True)
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)
        self.c2.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)
        self.c3.assert_no_ic()
        self.c4.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)

        self.c1.sic('Hallo there.')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hallo there.', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_no_ic()

        self.c2.sic('Hallo mate.')
        self.c4.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_ic('Hallo mate.', folder=self.c2_cname, over=True)
        self.c3.assert_no_ic()
        self.c4.assert_ic('Hallo mate.', folder=self.c2_cname, over=True)

    def test_04_moveinoutrange(self):
        """
        Situation: C4 moves out of C1's global IC range. C3 moves in range.
        C1 talks IC. C1, C2, C3 receive it.
        """

        self.c4.move_area(0)
        self.c3.move_area(5)

        self.c1.sic('>>>Hallo new mates.')
        self.c1.assert_ooc('Sent global IC message "Hallo new mates." to areas {} through {}.'
                           .format(self.a1_name, self.a5_name), ooc_over=True)
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hallo new mates.', folder=self.c1_cname, over=True)
        self.c2.assert_ic('Hallo new mates.', folder=self.c1_cname, over=True)
        self.c3.assert_ic('Hallo new mates.', folder=self.c1_cname, over=True)
        self.c4.assert_no_ic()

    def test_05_senderoutofrange(self):
        """
        Situation: C1 makes a new range in which they are not a part of.
        When they send IC messages, they do not receive them.
        """

        self.c1.ooc('/globalic {}, {}'.format(4, 5))
        self.c1.assert_ooc('Your IC messages will now be sent to areas {} through {}.'
                           .format(self.a4_name, self.a5_name))
        self.c1.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)

        self.c1.sic('>>>Hello players.')
        self.c1.assert_ooc('Sent global IC message "Hello players." to areas {} through {}.'
                           .format(self.a4_name, self.a5_name), over=True)
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_ic('Hello players.', folder=self.c1_cname, over=True)
        self.c3.assert_ic('Hello players.', folder=self.c1_cname, over=True)
        self.c4.assert_no_ic()

    def test_06_prefixwithnoglobalic(self):
        """
        Situation: C1 disables global IC. They keep the prefix active, but it does nothing.
        Players in the area see messages from C1 as is.
        """

        # C4 in same area as C1
        self.c4.move_area(1)

        self.c1.ooc('/unglobalic')
        self.c1.assert_ooc('Your IC messages will now be only sent to your current area.',
                           over=True)
        self.assertIsNone(self.c1.multi_ic)
        self.assertEqual(self.c1.multi_ic_pre, '>>>')

        self.c1.sic('Hello?')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hello?', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_ic('Hello?', folder=self.c1_cname, over=True)

        self.c1.sic('>>>Hello?')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('>>>Hello?', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_ic('>>>Hello?', folder=self.c1_cname, over=True)

    def test_07_changeprefixnoglobalic(self):
        """
        Situation: C1 changes their global IC prefix... while having no global IC. This succeeds.
        """

        # Change
        self.c1.ooc('/globalic_pre {}'.format('<<<'))
        self.c1.assert_ooc('You have set your global IC prefix to <<<', over=True)
        self.assertIsNone(self.c1.multi_ic)
        self.assertEqual(self.c1.multi_ic_pre, '<<<')

        self.c1.sic('Hello?')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hello?', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_ic('Hello?', folder=self.c1_cname, over=True)

        self.c1.sic('<<<Hello?')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('<<<Hello?', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_ic('<<<Hello?', folder=self.c1_cname, over=True)

        # Remove
        self.c1.ooc('/globalic_pre')
        self.c1.assert_ooc('You have removed your global IC prefix.', over=True)
        self.assertIsNone(self.c1.multi_ic)
        self.assertEqual(self.c1.multi_ic_pre, '')

        self.c1.sic('Hello?')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hello?', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_ic('Hello?', folder=self.c1_cname, over=True)

        self.c1.sic('<<<Hello?')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('<<<Hello?', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_ic('<<<Hello?', folder=self.c1_cname, over=True)

    def test_08_prefixbeforeglobalic(self):
        """
        Situation: C1 sets IC prefix before turning global IC. This works.
        """

        # C4 moves out of range.
        self.c4.move_area(0)

        self.c1.ooc('/globalic {}, {}'.format(1, 5))
        self.c1.assert_ooc('Your IC messages will now be sent to areas {} through {}.'
                           .format(self.a1_name, self.a5_name))
        self.c1.assert_ooc('Set up a global IC prefix with /globalic_pre', over=True)
        self.c1.ooc('/globalic_pre {}'.format('>>>'))
        self.c1.assert_ooc('You have set your global IC prefix to >>>', over=True)

        self.c1.sic('>>>Hallo mates.')
        self.c1.assert_ooc('Sent global IC message "Hallo mates." to areas {} through {}.'
                           .format(self.a1_name, self.a5_name), ooc_over=True)
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)
        self.c2.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)
        self.c3.assert_ic('Hallo mates.', folder=self.c1_cname, over=True)
        self.c4.assert_no_ic()

        self.c1.sic('Hallo there.')
        self.c1.assert_no_ooc()
        self.c0.assert_no_ic()
        self.c1.assert_ic('Hallo there.', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()
        self.c4.assert_no_ic()
