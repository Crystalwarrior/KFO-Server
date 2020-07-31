from .structures import _TestSituation5Mc1Gc2

class _TestRoll(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(4)
        cls.rolls = ['/roll', '/rollp']
        cls.def_numfaces = cls.server.config['def_numfaces']

    def bad_roll(self, arg, message):
        if isinstance(arg, int):
            arg = str(arg)

        for roll in self.rolls:
            self.c0.ooc('{} {}'.format(roll, arg))
            self.c0.assert_ooc(message.format(roll), over=True)
            self.c1.assert_no_ooc()
            self.c2.assert_no_ooc()
            self.c3.assert_no_ooc()
            self.c4.assert_no_ooc()

class _TestRoll_FixedRNG(_TestRoll):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expected_rolls = None

        class x():
            def __init__(self, expected_rolls=None):
                cls.expected_rolls = expected_rolls

            @staticmethod
            def randint(a, b):
                if not cls.expected_rolls:
                    raise KeyError('No expected rolls left for custom random object.')
                return cls.expected_rolls.pop(0)

        cls.randomer = x
        cls.server.random = x
        cls.do_roll = None # It is expected this is replaced by public_roll or private_roll in
        # test creation

    def do_roll(self, arg, expected_rolls, expected_result):
        self.roll_type(arg, expected_rolls, expected_result)

    def public_roll(self, arg, expected_rolls, expected_result):
        if isinstance(arg, int):
            arg = str(arg)

        dice_data = arg.split(' ')[0]
        expected_num_faces = int(dice_data.split('d')[-1]) if arg else self.def_numfaces
        expected_message = 'rolled {} out of {}'.format(expected_result, expected_num_faces)

        self.server.random = self.randomer(expected_rolls=expected_rolls)
        self.c0.ooc('/roll {}'.format(arg))
        self.c0.assert_ooc('You {}.'.format(expected_message), over=True)
        self.c1.assert_ooc('{} {}.'.format(self.c0_dname, expected_message), over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.c4.assert_ooc('{} {}.'.format(self.c0_dname, expected_message), over=True)

    def private_roll(self, arg, expected_rolls, expected_result):
        if isinstance(arg, int):
            arg = str(arg)

        dice_data = arg.split(' ')[0]
        expected_num_faces = int(dice_data.split('d')[-1]) if arg else self.def_numfaces
        expected_message = ('privately rolled {} out of {}'
                            .format(expected_result, expected_num_faces))

        self.server.random = self.randomer(expected_rolls=expected_rolls)
        self.c0.ooc('/rollp {}'.format(arg))
        self.c0.assert_ooc('You {}.'.format(expected_message), over=True)
        self.c1.assert_ooc('(X) {} [{}] {}.'.format(self.c0_dname, 0, expected_message), over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.c4.assert_ooc('Someone rolled.', over=True)

    def test01_nomodifiers(self):
        """
        Situation: Client calls roll without modifiers.
        """

        self.do_roll('20', [17], '17')
        self.do_roll('20', [1], '1')
        self.do_roll('3d20', [5, 5, 1], '(5, 5, 1)')

    def test02_modifiers(self):
        """
        Situation: Client calls roll with modifiers.
        """

        self.do_roll('20 +3', [16], '16:16+3=19')
        self.do_roll('20 +3', [19], '19:19+3=22')
        self.do_roll('20 -2', [4], '4:4-2=2')
        self.do_roll('20 -2', [2], '2:2-2=|1')

class TestRoll_01_WrongArguments(_TestRoll):
    """
    Since there are so many ways rolling can go wrong, an entire test class is dedicated to it.
    Whenever /roll is mentioned, /rollp is also implicitly suggested as having the same behavior
    unless explicitly mentioned otherwise.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.max_numdice = cls.server.config['max_numdice']
        cls.max_numfaces = cls.server.config['max_numfaces']
        cls.max_modifier_length = cls.server.config['max_modifier_length']
        cls.max_acceptable_term = cls.server.config['max_acceptable_term']
        cls.def_numdice = cls.server.config['def_numdice']
        cls.def_numfaces = cls.server.config['def_numfaces']
        cls.def_modifier = cls.server.config['def_modifier']

        cls.ACCEPTABLE_IN_MODIFIER = '1234567890+-*/().r'
        cls.MAXDIVZERO_ATTEMPTS = 10

    def test_01_toomanyarguments(self):
        """
        Situation: Client tries to use more than 2 arguments.
        """

        self.bad_roll('a b c',
                      'This command takes one or two arguments. '
                      'Use {} <num_dice>d<num_faces> <modifiers>')

    def test_02_badarguments(self):
        """
        Situation: Client tries to pass in meaningless arguments.
        """

        self.bad_roll('e',
                      'The number of rolls and faces of the dice must be positive integers.')
        self.bad_roll('15.6',
                      'The number of rolls and faces of the dice must be positive integers.')
        self.bad_roll('ed20',
                      'The number of rolls and faces of the dice must be positive integers.')
        self.bad_roll('2.4d20',
                      'The number of rolls and faces of the dice must be positive integers.')
        self.bad_roll('5*4',
                      'The number of rolls and faces of the dice must be positive integers.')
        self.bad_roll('20 3x', # x is not in self.ACCEPTABLE_IN_MODIFIER
                      'The modifier must only include numbers and standard mathematical operations '
                      'in the modifier.')
        self.bad_roll('20 +3**3', # Exponentiation is manually disabled
                      'The modifier must only include numbers and standard mathematical operations '
                      'in the modifier.')
        self.bad_roll('20 -1..4',
                      'The modifier has a syntax error.')

    def test_03_outsiderange(self):
        """
        Situation: Client tries to use arguments that are too small or too big.
        """

        self.bad_roll('20 {}'.format('3'*(self.max_modifier_length + 1)),
                      'The modifier is too long to compute. Please try a shorter one.')
        self.bad_roll(-1,
                      'Number of faces must be between 1 and {}.'.format(self.max_numfaces))
        self.bad_roll(0,
                      'Number of faces must be between 1 and {}.'.format(self.max_numfaces))
        self.bad_roll(self.max_numfaces + 1,
                      'Number of faces must be between 1 and {}.'.format(self.max_numfaces))
        self.bad_roll('{}d20'.format(0),
                      'Number of rolls must be between 1 and {}.'.format(self.max_numdice))
        self.bad_roll('{}d20'.format(-1),
                      'Number of rolls must be between 1 and {}.'.format(self.max_numdice))
        self.bad_roll('{}d20'.format(self.max_numdice + 1),
                      'Number of rolls must be between 1 and {}.'.format(self.max_numdice))
        self.bad_roll('20 +{}'.format(self.max_acceptable_term + 1),
                      'The modifier must take numbers within the computation limit of the server.')
        self.bad_roll('20 +1*{}/3'.format(self.max_acceptable_term + 1),
                      'The modifier must take numbers within the computation limit of the server.')

    def test_04_evaluationerror(self):
        """
        Situation: Client tries to use modifiers that do not make mathematical sense.
        """

        self.bad_roll('20 +*3',
                      'The modifier has a syntax error.')
        self.bad_roll('20 3(5-1)', # Python thinks this is a function
                      'The modifier has a syntax error.')
        self.bad_roll('20 1/0', # Division by zero
                      'The modifier causes divisions by zero too often.')

class TestRoll_02_PublicRoll(_TestRoll_FixedRNG):
    """
    Wrapper tester for /roll.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.do_roll = cls.public_roll

class TestRoll_03_PrivateRoll(_TestRoll_FixedRNG):
    """
    Wrapper tester for /rollp.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.do_roll = cls.private_roll

