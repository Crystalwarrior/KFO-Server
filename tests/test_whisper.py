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

    def get_identifiers(self, client):
        """
        Return a list containing the following elements, in order.
        1. The ID of `client`
        2. The character name of `client`
        3. The OOC name of `client`
        4. The character folder `client` is using if different from (2) (say, via iniediting)
        5. The showname of `client` if set
        """

        identifiers = [client.id, client.get_char_name(), client.name]
        if client.char_folder and client.char_folder != client.get_char_name():
            identifiers.append(client.char_folder)
        if client.showname:
            identifiers.append(client.showname)
        return identifiers

class TestWhisper_01_WhisperFailure(_TestWhisper):
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

    def test_02_whispermustbeinarea(self):
        """
        Situation: All players attempt to whisper to C3, who is by themselves in area 5. They all
        fail, including staff members.
        """

        senders = [self.c0, self.c1, self.c2, self.c4, self.c5]

        for sender in senders:
            for identifier in self.get_identifiers(self.c3):
                message = '{} with {} to {}'.format(sender, identifier, self.c3)
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc('No targets with identifier `{} {}` found.'
                                  .format(identifier, message), over=True)
                self.c3.assert_no_packets()

    def test_03_whisperermustnotbegagged(self):
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
            for identifier in self.get_identifiers(recipient):
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

    def test_04_nonstaffwhispertosneaked(self):
        """
        Situation: Just for this test, C4 starts sneaking. C0, who is in the same area as C4,
        attempts to whisper to C4. This fails.
        """

        self.c1.ooc('/sneak 4')
        self.c1.discard_all()
        self.c4.discard_all()

        for identifier in self.get_identifiers(self.c4):
            message = '{} with {} to {}'.format(self.c0, identifier, self.c4)
            self.c0.ooc('/whisper {} {}'.format(identifier, message))
            self.c0.assert_ooc('No targets with identifier `{} {}` found.'
                              .format(identifier, message), over=True)
            self.c1.assert_no_packets()
            self.c2.assert_no_packets()
            self.c3.assert_no_packets()
            self.c4.assert_no_packets()
            self.c5.assert_no_packets()

        self.c1.ooc('/reveal 4')
        self.c1.discard_all()
        self.c4.discard_all()

    def test_05_staffwhispertosneaked(self):
        """
        Situation: Just for this test, C4 starts sneaking. C1, who is in the same area as C4,
        attempts to whisper to C4. This fails, but with a different message, suggesting to use
        /guide instead.
        """

        self.c1.ooc('/sneak 4')
        self.c1.discard_all()
        self.c4.discard_all()

        for identifier in self.get_identifiers(self.c4):
            message = '{} with {} to {}'.format(self.c1, identifier, self.c4)
            self.c1.ooc('/whisper {} {}'.format(identifier, message))
            self.c1.assert_ooc('Your target {} is sneaking and whispering to them would reveal '
                               'them. Instead, use /guide'.format(self.c4.displayname), over=True)
            self.c0.assert_no_packets()
            self.c2.assert_no_packets()
            self.c3.assert_no_packets()
            self.c4.assert_no_packets()
            self.c5.assert_no_packets()

        self.c1.ooc('/reveal 4')
        self.c1.discard_all()
        self.c4.discard_all()

class TestWhisper_02_WhisperNormal(_TestWhisper):
    def test_01_whisperbothnonstaff(self):
        """
        Situation: C0 and C4 both whisper to one another, using all available identifiers.
        C1, C2 and C5 (all staff) get notified.
        """

        interactions = [(self.c0, self.c4), (self.c4, self.c0)]
        for (sender, recipient) in interactions:
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname)
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
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

    def test_02_whisperstaffandnonstaff(self):
        """
        Situation: C0 and C1 (mod) both whisper to one another, using all available identifiers.
        C2 and C5 (all staff) get notified. C4, being in the same area as C0 and C1, but not staff,
        receives nerfed messages. C1 does NOT get the special staff OOC message (they already get
        one by virtue of being sender/recipient).
        """

        interactions = [(self.c0, self.c1), (self.c1, self.c0)]
        for (sender, recipient) in interactions:
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname)
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
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

    def test_03_whisperbetweenstaff(self):
        """
        Situation: C2 and C5 (both staff) whisper to one another, using all available identifiers.
        C1 (the only other staff) is notified. C0, C3, C4 are non-staff not in the area, so they do
        not get notified. C2 and C5 do NOT get the special staff OOC message (they already get
        one by virtue of being sender/recipient).
        """

        interactions = [(self.c2, self.c5), (self.c5, self.c2)]
        for (sender, recipient) in interactions:
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname)
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
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

    def test_04_whisperfromsneakedtononsneaked(self):
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
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = ('You spooked {} by whispering `{}` to them while sneaking.'
                            .format(recipient.displayname, message))
                recipient_ooc = ('You heard a whisper and you think it was directed at you, but '
                                 'you could not seem to tell where it came from.')
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} while sneaking ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
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

    def test_05_selfwhisper(self):
        """
        Situation: Every client whispers to themselves. Only they themselves get the notification.
        """

        for client in self.server.client_manager.clients:
            for identifier in self.get_identifiers(client):
                message = '{} with {} to {}'.format(client, identifier, client)
                ooc = 'You whispered `{}` to yourself.'.format(message)
                client.ooc('/whisper {} {}'.format(identifier, message))
                client.assert_ooc(ooc, ooc_over=True)
                client.assert_ic(message, folder="<NOCHAR>", pos=client.pos,
                                 showname=client.showname, cid=client.char_id, over=True)

    def test_06_whispersneakedtosneakedparty(self):
        """
        Situation: Just for this test, C2 and C3 move to C0's area and C2 is made a normie.
        C0 and C4 form a party, C3 another one, and C2 remains partyless.
        C0, C2, C3, C4 all start sneaking.
        They all try to whisper to one another. Only C0-C4 succeed, and for them, all staff (C1 and
        C5) are notified.
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
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = '{} whispered something to you.'.format(sender.displayname)
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} while both were sneaking and part '
                             'of the same party ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
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
            for identifier in self.get_identifiers(recipient):
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

class TestWhisper_03_WhisperToDeafened(_TestWhisper):
    # The following people are assumed deafened throughout this test class
    # C0
    # C4
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c1.ooc('/deafen 0')
        cls.c1.ooc('/deafen 4')
        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()
        cls.c4.discard_all()
        cls.c5.discard_all()

    def test_01_whisperbothnonstaff(self):
        """
        Situation: C0 and C4 (both deafened) both whisper to one another, using all available
        identifiers. C1, C2 and C5 (all staff) get notified. This also tests a symmetrical deafened
        status (both sender/recipient are deafened).
        """

        interactions = [(self.c0, self.c4), (self.c4, self.c0)]
        for (sender, recipient) in interactions:
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = ('{} seemed to whisper something to you, but you could not make it '
                                 'out.'.format(sender.displayname))
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
                                     sender.area.id))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic('(Your ears are ringing)', folder='<NOCHAR>', pos=sender.pos,
                                 cid=sender.char_id, showname=sender.showname,
                                 allow_partial_match=True, over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic('(Your ears are ringing)', folder='<NOCHAR>', pos=sender.pos,
                                    cid=sender.char_id, showname=sender.showname,
                                    allow_partial_match=True, over=True)
                self.c1.assert_ooc(staff_ooc, over=True)
                self.c2.assert_ooc(staff_ooc, over=True)
                self.c3.assert_no_packets()
                self.c5.assert_ooc(staff_ooc, over=True)

    def test_02_whisperstaffandnonstaff(self):
        """
        Situation: C0 and C1 (mod) both whisper to one another, using all available identifiers.
        C2 and C5 (all staff) get notified. C4, being in the same area as C0 and C1, but not staff,
        receives nerfed messages. C1 does NOT get the special staff OOC message (they already get
        one by virtue of being sender/recipient). This also tests an aymmetrical deafened status
        (only one of sender/recipient is deafened).
        """

        sender, recipient = self.c0, self.c1
        for identifier in self.get_identifiers(recipient):
            message = '{} with {} to {}'.format(sender, identifier, recipient)
            sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
            recipient_ooc = '{} whispered something to you.'.format(sender.displayname)
            staff_ooc = ('(X) {} [{}] whispered `{}` to {} ({}).'
                         .format(sender.displayname, sender.id, message, recipient.displayname,
                                 sender.area.id))
            nonstaff_ooc = ('{} whispered something to {}.'
                             .format(sender.displayname, recipient.displayname))
            sender.ooc('/whisper {} {}'.format(identifier, message))
            sender.assert_ooc(sent_ooc, ooc_over=True)
            sender.assert_ic('(Your ears are ringing)', folder='<NOCHAR>', pos=sender.pos,
                             cid=sender.char_id, showname=sender.showname,
                             allow_partial_match=True, over=True)
            recipient.assert_ooc(recipient_ooc, ooc_over=True)
            recipient.assert_ic(message, folder='<NOCHAR>', pos=sender.pos, cid=sender.char_id,
                                showname=sender.showname, over=True)
            self.c2.assert_ooc(staff_ooc, over=True)
            self.c3.assert_no_packets()
            self.c4.assert_ooc(nonstaff_ooc, over=True)
            self.c5.assert_ooc(staff_ooc, over=True)

    def test_03_whisperfromsneakedtononsneaked(self):
        """
        Situation: C3 moves to C0's area for this test. C3 starts sneaking and whispering to C4,
        using all available identifiers. C1, C2 and C5 (all staff) get notified. C0 gets no
        notifications.
        """

        self.c3.move_area(0)

        self.c1.ooc('/sneak 3')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c5.discard_all()

        interactions = [(self.c3, self.c4)]
        for (sender, recipient) in interactions:
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = ('You spooked {} by whispering `{}` to them while sneaking.'
                            .format(recipient.displayname, message))
                recipient_ooc = 'Your ears seemed to pick up something.'
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} while sneaking ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
                                     sender.area.id))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic(message, folder='<NOCHAR>', pos='jud', showname='???', over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic('(Your ears are ringing)', folder='<NOCHAR>', pos='jud',
                                    allow_partial_match=True, showname='???', over=True)
                self.c0.assert_no_packets()
                self.c1.assert_ooc(staff_ooc, over=True)
                self.c2.assert_ooc(staff_ooc, over=True)
                self.c5.assert_ooc(staff_ooc, over=True)

        # Restore original state
        self.c1.ooc('/reveal 3')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()
        self.c3.move_area(5)

    def test_04_selfwhisper(self):
        """
        Situation: Every deafened client whispers to themselves. Only they themselves get the
        notification, as well as a nerfed IC message.
        """

        for client in [self.c0, self.c4]:
            for identifier in self.get_identifiers(client):
                message = '{} with {} to {}'.format(client, identifier, client)
                ooc = 'You whispered `{}` to yourself.'.format(message)
                client.ooc('/whisper {} {}'.format(identifier, message))
                client.assert_ooc(ooc, ooc_over=True)
                client.assert_ic('(Your ears are ringing)', folder="<NOCHAR>", pos=client.pos,
                                 showname=client.showname, cid=client.char_id,
                                 allow_partial_match=True, over=True)

    def test_05_whispersneakedtosneakedparty(self):
        """
        Situation: Just for this test, C2 and C3 move to C0's area and C2 is made a normie.
        C0 and C4 form a party, C3 another one, and C2 remains partyless.
        C0, C2, C3, C4 all start sneaking.
        They all try to whisper to one another. Only C0-C4 succeed at getting a whisper out, but
        as they are all deaf, their messages net nerfed. All staff (C1 and C5) are notified.
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
            for identifier in self.get_identifiers(recipient):
                message = '{} with {} to {}'.format(sender, identifier, recipient)
                sent_ooc = 'You whispered `{}` to {}.'.format(message, recipient.displayname)
                recipient_ooc = ('{} seemed to whisper something to you, but you could not make it '
                                 'out.'.format(sender.displayname))
                staff_ooc = ('(X) {} [{}] whispered `{}` to {} while both were sneaking and part '
                             'of the same party ({}).'
                             .format(sender.displayname, sender.id, message, recipient.displayname,
                                     sender.area.id))
                sender.ooc('/whisper {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, ooc_over=True)
                sender.assert_ic('(Your ears are ringing)', folder='<NOCHAR>', pos=sender.pos,
                                 cid=sender.char_id, showname=sender.showname,
                                 allow_partial_match=True, over=True)
                recipient.assert_ooc(recipient_ooc, ooc_over=True)
                recipient.assert_ic('(Your ears are ringing)', folder='<NOCHAR>', pos=sender.pos,
                                    cid=sender.char_id, showname=sender.showname,
                                    allow_partial_match=True, over=True)
                self.c1.assert_ooc(staff_ooc, over=True)
                self.c2.assert_no_packets()
                self.c3.assert_no_packets()
                self.c5.assert_ooc(staff_ooc, over=True)

        # Unsuccessful because other type of party interaction
        interactions = [(self.c0, self.c2), (self.c2, self.c3), (self.c3, self.c4),
                        (self.c4, self.c2), (self.c3, self.c0), (self.c4, self.c3) ]

        for (sender, recipient) in interactions:
            for identifier in self.get_identifiers(recipient):
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

class TestWhisper_04_Guide(_TestWhisper):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to guide incorrectly.
        """

        mes = ('Not enough arguments. Use /guide <target> <message>. Target should be '
               'ID, char-name, edited-to character, custom showname or OOC-name.')

        # Not staff
        self.c0.ooc('/guide 4 Hallo')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No target
        self.c1.ooc('/guide')
        self.c0.assert_no_packets()
        self.c1.assert_ooc(mes, over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No message
        self.c1.ooc('/guide 0')
        self.c0.assert_no_packets()
        self.c1.assert_ooc(mes, over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No target
        self.c1.ooc('/guide 100 Test')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('No targets with identifier `100 Test` found.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Target is self
        self.c1.ooc('/guide 1 Test')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You cannot guide yourself.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_guidenonstaff(self):
        """
        Situation: C1 guides all non-staff, even those not in C1's area. All other staff (C2, C5)
        are notified, but none of the staff are.
        """

        sender = self.c1
        for target in [self.c0, self.c4]:
            for identifier in self.get_identifiers(target):
                message = '{} with {} to {}'.format(sender, identifier, target)
                sent_ooc = ('You gave the following guidance to {}: `{}`.'
                            .format(target.displayname, message))
                target_ooc = 'You hear a guiding voice in your head.'
                staff_ooc = ('(X) {} [{}] gave the following guidance to {}: `{}` ({}).'
                             .format(sender.displayname, sender.id, target.displayname, message,
                                     sender.area.id))

                sender.ooc('/guide {} {}'.format(identifier, message))
                sender.assert_ooc(sent_ooc, over=True)
                target.assert_ooc(target_ooc, ooc_over=True)
                target.assert_ic(message, folder='<NOCHAR>', over=True)
                self.c2.assert_ooc(staff_ooc, over=True)
                self.c3.assert_no_packets()
                self.c5.assert_ooc(staff_ooc, over=True)

        target = self.c3 # Non-staff not in c0's area
        identifier = '3' # Client ID is the only identifier that will work
        message = '{} with {} to {}'.format(sender, identifier, target)
        sent_ooc = ('You gave the following guidance to {}: `{}`.'
                    .format(target.displayname, message))
        target_ooc = 'You hear a guiding voice in your head.'
        staff_ooc = ('(X) {} [{}] gave the following guidance to {}: `{}` ({}).'
                     .format(sender.displayname, sender.id, target.displayname, message,
                             sender.area.id))

        sender.ooc('/guide {} {}'.format(identifier, message))
        sender.assert_ooc(sent_ooc, over=True)
        target.assert_ooc(target_ooc, ooc_over=True)
        target.assert_ic(message, folder='<NOCHAR>', over=True)
        self.c2.assert_ooc(staff_ooc, over=True)
        self.c3.assert_no_packets()
        self.c5.assert_ooc(staff_ooc, over=True)

    def test_03_guidestaff(self):
        """
        Situation: C2 guides all other staff, even those not in C2's area. The other staff is
        notified, but none all of the other staff.
        """

        sender = self.c2
        for (target, not_st_target) in [(self.c1, self.c5), (self.c5, self.c1)]:
            identifier = target.id
            message = '{} with {} to {}'.format(sender, identifier, target)
            sent_ooc = ('You gave the following guidance to {}: `{}`.'
                        .format(target.displayname, message))
            target_ooc = 'You hear a guiding voice in your head.'
            staff_ooc = ('(X) {} [{}] gave the following guidance to {}: `{}` ({}).'
                         .format(sender.displayname, sender.id, target.displayname, message,
                                 sender.area.id))

            sender.ooc('/guide {} {}'.format(identifier, message))
            sender.assert_ooc(sent_ooc, over=True)
            target.assert_ooc(target_ooc, ooc_over=True)
            target.assert_ic(message, folder='<NOCHAR>', over=True)
            not_st_target.assert_ooc(staff_ooc, over=True)
            self.c0.assert_no_packets()
            self.c3.assert_no_packets()
            self.c4.assert_no_packets()
