from .structures import _TestSituation6Mc1Gc25

class _TestWhisper(_TestSituation6Mc1Gc25):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(5)
        cls.c5.move_area(4)

        # C0, C1 (m) and C4 are in area 0
        # C2 (gm), C5 (gm) are in area 4
        # C3 is in area 5

class TestWhisper_01_WhisperBasic(_TestWhisper):
    def test_01_wrongarguments(self):
        """
        Situation: C0 attempts to whisper incorrectly.
        """

        mes = ('Not enough arguments. Use /whisper <target> <message>. Target should be '
               'ID, char-name, edited-to character, custom showname or OOC-name.')

        # No target
        self.c0.ooc('/whisper')
        self.c0.assert_ooc(mes, over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # No message
        self.c0.ooc('/whisper 1')
        self.c0.assert_ooc(mes, over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # No target
        self.c0.ooc('/whisper 100 Test')
        self.c0.assert_ooc('No targets with identifier `100 Test` found.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_whisperbothnonstaff(self):
        """
        Situation: C0 and C4 both whisper to one another, using all available identifiers.
        C1, C2 and C5 (all staff) get notified.
        """

        interactions = [(self.c0, self.c4), (self.c4, self.c0)]
        for (sender, recipient) in interactions:
            identifiers = [recipient.id, recipient.get_char_name(), recipient.name]
            if recipient.char_folder and recipient.char_folder != recipient.get_char_name():
                identifiers.append(recipient.char_folder)
            if recipient.showname:
                identifiers.append(recipient.showname)

            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname, message)
                staff_ooc = ('(X) {} whispered `{}` to {} ({}).'
                             .format(sender.displayname, message, recipient.displayname,
                                     sender.area.id))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                 showname=sender.showname, over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                    showname=sender.showname, over=True)
                self.c1.assert_ooc(staff_ooc, over=True)
                self.c2.assert_ooc(staff_ooc, over=True)
                self.c3.assert_no_packets()
                self.c5.assert_ooc(staff_ooc, over=True)

    def test_03_whisperstaffandnonstaff(self):
        """
        Situation: C0 and C1 (mod) both whisper to one another, using all available identifiers.
        C2 and C5 (all staff) get notified. C4, being in the same area as C0 and C1, but not staff,
        receives nerfed messages. C1 does NOT get the special staff OOC message (they already get
        one by virtue of being sender/recipient).
        """

        interactions = [(self.c0, self.c1), (self.c1, self.c0)]
        for (sender, recipient) in interactions:
            identifiers = [recipient.id, recipient.get_char_name(), recipient.name]
            if recipient.char_folder and recipient.char_folder != recipient.get_char_name():
                identifiers.append(recipient.char_folder)
            if recipient.showname:
                identifiers.append(recipient.showname)

            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname, message)
                staff_ooc = ('(X) {} whispered `{}` to {} ({}).'
                             .format(sender.displayname, message, recipient.displayname,
                                     sender.area.id))
                nonstaff_ooc = ('{} whispered something to {}.'
                                 .format(sender.displayname, recipient.displayname))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                 showname=sender.showname, over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                    showname=sender.showname, over=True)
                self.c2.assert_ooc(staff_ooc, over=True)
                self.c3.assert_no_packets()
                self.c4.assert_ooc(nonstaff_ooc, over=True)
                self.c5.assert_ooc(staff_ooc, over=True)

    def test_04_whisperbetweenstaff(self):
        """
        Situation: C2 and C5 (both staff) whisper to one another, using all available identifiers.
        C1 (the only other staff) is notified. C0, C3, C4 are non-staff not in the area, so they do
        not get notified. C2 and C5 do NOT get the special staff OOC message (they already get
        one by virtue of being sender/recipient).
        """

        interactions = [(self.c2, self.c5), (self.c5, self.c2)]
        for (sender, recipient) in interactions:
            identifiers = [recipient.id, recipient.get_char_name(), recipient.name]
            if recipient.char_folder and recipient.char_folder != recipient.get_char_name():
                identifiers.append(recipient.char_folder)
            if recipient.showname:
                identifiers.append(recipient.showname)

            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname, message)
                staff_ooc = ('(X) {} whispered `{}` to {} ({}).'
                             .format(sender.displayname, message, recipient.displayname,
                                     sender.area.id))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                 showname=sender.showname, over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                    showname=sender.showname, over=True)
                self.c1.assert_ooc(staff_ooc, over=True)
                self.c3.assert_no_packets()
                self.c4.assert_no_packets()
                self.c5.assert_no_packets()

class TestWhisper_02_WhisperSpecial(_TestWhisper):
    def test_01_whispermustbeinarea(self):
        """
        Situation: All players attempt to whisper to C3, who is by themselves in area 5. They all
        fail, including staff members.
        """

        senders = [self.c0, self.c1, self.c2, self.c4, self.c5]
        identifiers = [self.c3.id, self.c3.get_char_name(), self.c3.name]
        if self.c3.char_folder and self.c3.char_folder != self.c3.get_char_name():
            identifiers.append(self.c3.char_folder)
        if self.c3.showname:
            identifiers.append(self.c3.showname)

        for sender in senders:
            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, self.c3)
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc('No targets with identifier `{} {}` found.'
                                  .format(identifier, message), over=True)
                self.c3.assert_no_packets()

    def test_02_whisperermustnotbegagged(self):
        """
        Situation: C0 and C5 are gagged for this test. C0 and C5 attempt to whisper to people in
        their areas. They all fail, and only they receive notifications.
        """

        self.c1.ooc('/gag 0')
        self.c1.ooc('/gag 5')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        interactions = [(self.c0, self.c4), (self.c5, self.c2)]

        for (sender, recipient) in interactions:
            identifiers = [recipient.id, recipient.get_char_name(), recipient.name]
            if recipient.char_folder and recipient.char_folder != recipient.get_char_name():
                identifiers.append(recipient.char_folder)
            if recipient.showname:
                identifiers.append(recipient.showname)

            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, self.c3)
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc('Your attempt at whispering failed because you are gagged.',
                                  over=True)
                recipient.assert_no_packets()

        self.c1.ooc('/gag 0')
        self.c1.ooc('/gag 5')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

    def test_03_whisperfromsneakedtononsneaked(self):
        """
        Situation: C3 moves to C0's area for this test. C0 starts sneaking and whispering to C4,
        using all  available identifiers. C1, C2 and C5 (all staff) get notified. C3 gets no
        notifications.
        """

        self.c3.move_area(0)

        self.c1.ooc('/sneak 0')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        interactions = [(self.c0, self.c4)]
        for (sender, recipient) in interactions:
            identifiers = [recipient.id, recipient.get_char_name(), recipient.name]
            if recipient.char_folder and recipient.char_folder != recipient.get_char_name():
                identifiers.append(recipient.char_folder)
            if recipient.showname:
                identifiers.append(recipient.showname)

            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = ('You spooked {} by whispering `{}` to them while sneaking.'
                            .format(recipient.displayname, message))
                recipient_ooc = ('You heard a whisper and you think it is directed at you, but you '
                                 'could not seem to tell where it came from.')
                staff_ooc = ('(X) {} whispered `{}` to {} while sneaking ({}).'
                             .format(sender.displayname, message, recipient.displayname,
                                     sender.area.id))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic(message, folder='<NOCHAR>', pos='jud', showname='???', over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic(message, folder='<NOCHAR>', pos='jud', showname='???',
                                    over=True)
                self.c1.assert_ooc(staff_ooc, over=True)
                self.c2.assert_ooc(staff_ooc, over=True)
                self.c3.assert_no_packets()
                self.c5.assert_ooc(staff_ooc, over=True)

        # Restore original state
        self.c1.ooc('/reveal 0')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()
        self.c3.move_area(5)

    def test_04_whispersneakedtosneakedparty(self):
        """
        Situation: C2 and C3 move to C0's area for this test and C2 is made a normie.
        C0 and C4 form a party, C3 another one, and C2 remains partyless.
        C0, C2, C3, C4 all start sneaking.
        They all try to whisper to one another. Only C0-C4 succeed, and for them, all staff (C1 and
        C5 are notified).
        """
        self.c3.move_area(0)
        self.c2.move_area(0)
        self.c2.make_normie()

        self.c0.ooc('/party')
        _, p = self.c0.search_match((self.server.config['hostname'], 'You have created party'),
                                    self.c0.received_ooc, somewhere=True, remove_match=False,
                                    allow_partial_match=True)
        party_number = p[1].split(' ')[-1][:-1] # Temporary, will improve later
        self.c0.ooc('/party_invite 4')
        self.c4.ooc('/party_join {}'.format(party_number))
        self.c3.ooc('/party')

        self.c1.ooc('/sneak 0')
        self.c1.ooc('/sneak 2')
        self.c1.ooc('/sneak 3')
        self.c1.ooc('/sneak 4')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()
        self.c5.discard_all()

        # Successful
        interactions = [(self.c0, self.c4), (self.c4, self.c0)]
        for (sender, recipient) in interactions:
            identifiers = [recipient.id, recipient.get_char_name(), recipient.name]
            if recipient.char_folder and recipient.char_folder != recipient.get_char_name():
                identifiers.append(recipient.char_folder)
            if recipient.showname:
                identifiers.append(recipient.showname)

            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname, message)
                staff_ooc = ('(X) {} whispered `{}` to {} while both were sneaking and part of the '
                             'same party ({}).'
                             .format(sender.displayname, message, recipient.displayname,
                                     sender.area.id))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                 showname=sender.showname, over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                    showname=sender.showname, over=True)
                self.c1.assert_ooc(staff_ooc, over=True)
                self.c2.assert_no_packets()
                self.c3.assert_no_packets()
                self.c5.assert_ooc(staff_ooc, over=True)

        # Unsuccessful because other type of party interaction
        interactions = [(self.c0, self.c2), (self.c2, self.c3), (self.c3, self.c4),
                        (self.c4, self.c2), (self.c3, self.c0), (self.c4, self.c3) ]

        for (sender, recipient) in interactions:
            identifiers = [recipient.id, recipient.get_char_name(), recipient.name]
            if recipient.char_folder and recipient.char_folder != recipient.get_char_name():
                identifiers.append(recipient.char_folder)
            if recipient.showname:
                identifiers.append(recipient.showname)

            for identifier in identifiers:
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc('No targets with identifier `{} {}` found.'
                                  .format(identifier, message), over=True)
                recipient.assert_no_packets()

        # Restore original state
        self.c1.ooc('/reveal 0')
        self.c1.ooc('/reveal 2')
        self.c1.ooc('/reveal 3')
        self.c1.ooc('/reveal 4')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()
        self.c5.discard_all()
        self.c2.move_area(4)
        self.c3.move_area(5)
        self.c2.make_gm()