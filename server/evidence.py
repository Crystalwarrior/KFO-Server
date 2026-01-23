from server import commands
from server.exceptions import ClientError, AreaError, ArgumentError, ServerError


class EvidenceList:
    """Contains a list of evidence items."""

    limit = 50

    class Evidence:
        """Represents a single evidence item."""

        def __init__(self, name, desc, image, pos, can_hide_in=False, show_in_dark=0, triggers=None):
            self.name = name
            self.desc = desc
            self.image = image
            self.public = False
            self.pos = pos
            self.can_hide_in = can_hide_in
            self.show_in_dark = show_in_dark
            self.hiding_client = None
            self.triggers = triggers
            if triggers is None:
                self.triggers = {}

        def set_name(self, name):
            self.name = name

        def set_desc(self, desc):
            self.desc = desc

        def set_image(self, image):
            self.image = image

        def to_tuple(self):
            """Serialize data to the AO protocol."""
            return (self.name, self.desc, self.image)

        def to_dict(self):
            return {
                "name": self.name,
                "desc": self.desc,
                "image": self.image,
                "pos": self.pos,
                "can_hide_in": self.can_hide_in,
                "show_in_dark": self.show_in_dark,
                "triggers": self.triggers,
            }

        def trigger(self, area, trig, target):
            """Call the trigger's associated command."""
            if target.hidden:
                return

            if len(area.owners) <= 0:
                return

            if trig not in self.triggers:
                return

            arg = self.triggers[trig]
            if arg == "":
                return

            # Sort through all the owners, with GMs coming first and CMs coming second
            sorted_owners = list(area._owners) + list(area.area_manager.owners)

            # Pick the owner with highest permission - game master, if one exists.
            # This permission system may be out of wack, but it *should* be good for now
            owner = sorted_owners[0]

            arg = (
                arg.replace("<cid>", str(target.id))
                .replace("<showname>", target.showname)
                .replace("<char>", target.char_name)
            )
            args = arg.split(" ")
            cmd = args.pop(0).lower()
            if len(args) > 0:
                arg = " ".join(args)[:1024]
            try:
                old_area = owner.area
                old_hub = owner.area.area_manager
                owner.area = area
                commands.call(owner, cmd, arg)
                if old_area and old_area in old_hub.areas:
                    owner.area = old_area
            except (ClientError, AreaError, ArgumentError, ServerError) as ex:
                owner.send_ooc(f"[Area {area.id}] {ex}")
            except Exception as ex:
                owner.send_ooc(
                    f"[Area {area.id}] An internal error occurred: {ex}. Please inform the staff of the server about the issue."
                )

    def __init__(self):
        self.evidences = []

    def can_see(self, evi, pos):  # used with hiddenCM ebidense
        pos = pos.strip(" ")
        for p in evi.pos.strip(" ").split(","):
            if p == "all" or (pos != "" and pos == p):
                return True
        return False

    def can_hide_in(self, evi):
        return evi.can_hide_in

    def show_in_dark(self, evi):
        return evi.show_in_dark

    def login(self, client):
        """
        Determine whether or not evidence can be modified.
        :param client: origin

        """
        if client.area.evidence_mod == "FFA" or client.area.evidence_mod == "HiddenCM":
            return True
        elif client.area.evidence_mod == "Mods" and not client.is_mod:
            return False
        elif client.area.evidence_mod == "CM" and client not in client.area.owners and not client.is_mod:
            return False
        return True

    def correct_format(self, client, desc):
        """
        Check whether or not an evidence item contains a correct
        `<owner = [pos]>` metadata, if HiddenCM mode is on.
        :param client: origin
        :param desc: evidence description

        """
        if client.area.evidence_mod != "HiddenCM":
            return True
        # correct format: <owner=pos,pos,pos>\ndesc
        lines = desc.split("\n")
        cmd = lines[0].strip(" ")  # remove all whitespace
        if cmd[:7] == "<owner=" and cmd.endswith(">"):
            return True
        return False

    def parse_desc(self, desc):
        lines = desc.split("\n", 3)
        poses = "hidden"
        can_hide_in = 0
        show_in_dark = 0
        matches = 0
        for line in lines:
            cmd = line.strip(" ")  # remove all whitespace
            if cmd.startswith("<") and cmd.endswith(">"):
                args = cmd.strip("<>").split("=")
                if len(args) < 2:
                    break
                key, value = args
                if key == "owner":
                    if value == "":
                        value = "hidden"
                    poses = value
                    matches += 1
                if key == "can_hide_in":
                    can_hide_in = value == "1"
                    matches += 1
                if key == "show_in_dark":
                    show_in_dark = int(value)
                    matches += 1
        # Remvoes N lines, where N is how many <> we matched. Can't be more than 3.
        while matches > 0:
            # Truncates from the start of newline
            desc = desc[desc.find("\n") + 1 :]
            matches -= 1
        return desc, poses, can_hide_in, show_in_dark

    def add_evidence(self, client, name, desc, image):
        """
        Add an evidence item.
        :param client: origin
        :param name: evidence name
        :param description: evidence description
        :param image: evidence image file
        :param pos: positions for which evidence will be shown
        (Default value = 'all')

        """
        if not self.login(client):
            return
        if not client.is_mod and client not in client.area.owners:
            if client.area.dark:
                return
        if len(self.evidences) >= self.limit:
            client.send_ooc(f"You can't have more than {self.limit} evidence items at a time.")
            return
        can_hide_in = False
        show_in_dark = 0
        pos = "all"

        if client.area.evidence_mod == "HiddenCM":
            if client in client.area.owners or client.is_mod:
                pos = "hidden"
                if self.correct_format(client, desc):
                    desc, pos, can_hide_in, show_in_dark = self.parse_desc(desc)
            else:
                if len(client.area.pos_lock) > 0 and client.pos in client.area.pos_lock:
                    pos = client.pos

        self.evidences.append(self.Evidence(name, desc, image, pos, can_hide_in, show_in_dark))
        id = len(self.evidences)
        # Inform the CMs of evidence manupulation
        client.area.send_owner_command(
            "CT",
            client.server.config["hostname"],
            f"[{client.id}] {client.showname} added evidence {id}: {name} in area [{client.area.id}] {client.area.name}.",
            "1",
        )
        # send_owner_command does not tell CMs present in the area about evidence manipulation, so let's do that manually
        for c in client.area.owners:
            if c in client.area.clients:
                c.send_command(
                    "CT",
                    client.server.config["hostname"],
                    f"[{client.id}] {client.showname} added evidence {id}: {name} in this area.",
                    "1",
                )

    def evidence_swap(self, client, id1, id2):
        """
        Swap two evidence items.
        :param client: origin
        :param id1: evidence ID 1
        :param id2: evidence ID 2

        """
        if not self.login(client):
            return
        if id1 not in range(len(self.evidences)):
            return
        if id2 not in range(len(self.evidences)):
            return
        self.evidences[id1], self.evidences[id2] = (
            self.evidences[id2],
            self.evidences[id1],
        )

        # Inform the CMs of evidence manupulation
        client.area.send_owner_command(
            "CT",
            client.server.config["hostname"],
            f"[{client.id}] {client.showname} swapped evidence {id1 + 1}: {self.evidences[id1].name} with {id2 + 1}: {self.evidences[id2].name} in area [{client.area.id}] {client.area.name}.",
            "1",
        )
        # send_owner_command does not tell CMs present in the area about evidence manipulation, so let's do that manually
        for c in client.area.owners:
            if c in client.area.clients:
                c.send_command(
                    "CT",
                    client.server.config["hostname"],
                    f"[{client.id}] {client.showname} swapped evidence {id1 + 1}: {self.evidences[id1].name} with {id2 + 1}: {self.evidences[id2].name} in this area.",
                    "1",
                )

    def create_evi_list(self, client):
        """
        Compose an evidence list to send to a client.
        :param client: client to send list to

        """
        evi_list = []
        nums_list = [0]
        for i in range(len(self.evidences)):
            if client in client.area.owners or client.is_mod:
                nums_list.append(i + 1)
                evi = self.evidences[i]
                desc = evi.desc
                if client.area.evidence_mod == "HiddenCM":
                    can_hide_in = int(evi.can_hide_in)
                    show_in_dark = int(evi.show_in_dark)
                    desc = f"<owner={evi.pos}>\n<can_hide_in={can_hide_in}>\n<show_in_dark={show_in_dark}>\n{evi.desc}"
                evi_list.append(self.Evidence(evi.name, desc, evi.image, evi.pos).to_tuple())
            elif self.can_see(self.evidences[i], client.pos):
                # show_in_dark:
                # 0 - Do not show evidence in dark areas.
                # 1 - Show evidence in dark areas.
                # 2 - ONLY show evidence in dark areas. Will be hidden in non-dark areas.
                if client.area.dark and self.evidences[i].show_in_dark == 0:
                    continue
                if not client.area.dark and self.evidences[i].show_in_dark == 2:
                    continue
                nums_list.append(i + 1)
                evi_list.append(self.evidences[i].to_tuple())
        return nums_list, evi_list

    def import_evidence(self, data):
        for evi in data:
            name, desc, image, pos, can_hide_in, show_in_dark, triggers = "<name>", "<desc>", "", "all", False, 0, {}
            if "name" in evi:
                name = evi["name"]
            if "desc" in evi:
                desc = evi["desc"]
            if "image" in evi:
                image = evi["image"]
            if "pos" in evi:
                pos = evi["pos"]
            if "can_hide_in" in evi:
                can_hide_in = evi["can_hide_in"] is True
            if "show_in_dark" in evi:
                show_in_dark = int(evi["show_in_dark"])
            if "triggers" in evi:
                triggers = evi["triggers"]
            self.evidences.append(self.Evidence(name, desc, image, pos, can_hide_in, show_in_dark, triggers))

    def export_evidence(self):
        return [e.to_dict() for e in self.evidences]

    def del_evidence(self, client, id):
        """
        Delete an evidence item.
        :param client: origin
        :param id: evidence ID

        """
        if not self.login(client):
            return
        if not client.is_mod and client not in client.area.owners:
            if client.area.dark:
                return
        if id not in range(len(self.evidences)):
            return
        word = "deleted"
        if not client.is_mod and client not in client.area.owners:
            id = client.evi_list[id + 1] - 1
            evi = self.evidences[id]
            if client.area.evidence_mod == "HiddenCM":
                if evi.pos != "hidden":
                    client.add_inventory_evidence(evi.name, evi.desc, evi.image)
                    client.send_ooc(f"You take {evi.name} into your /inventory!")
                    word = "took"

                    evi.name = f"🚮{evi.name}"
                    evi.desc = f"(🚮Deleted by [{client.id}] {client.showname} ({client.name}))\n{evi.desc}"
                    evi.pos = "hidden"
            else:
                self.evidences.pop(id)
        else:
            evi = self.evidences[id]
            self.evidences.pop(id)

        # Inform the CMs of evidence manupulation
        client.area.send_owner_command(
            "CT",
            client.server.config["hostname"],
            f"[{client.id}] {client.showname} {word} evidence {id + 1}: {evi.name} in area [{client.area.id}] {client.area.name}.",
            "1",
        )
        # send_owner_command does not tell CMs present in the area about evidence manipulation, so let's do that manually
        for c in client.area.owners:
            if c in client.area.clients:
                c.send_command(
                    "CT",
                    client.server.config["hostname"],
                    f"[{client.id}] {client.showname} {word} evidence {id + 1}: {evi.name} in this area.",
                    "1",
                )

        c = evi.hiding_client
        if c is not None:
            c.hide(False)
            c.area.broadcast_area_list(c)
            c.send_ooc(f"You discover {c.showname} in the {evi.name}!")

    def edit_evidence(self, client, id, arg):
        """
        Modify an evidence item.
        :param client: origin
        :param id: evidence ID
        :param arg: evidence information

        """
        if not self.login(client):
            return

        name = arg[0]
        desc = arg[1]
        image = arg[2]
        pos = arg[3]

        can_hide_in = False
        show_in_dark = 0
        if client in client.area.owners or client.is_mod:
            if id not in range(len(self.evidences)):
                return
            evi = self.evidences[id]
            old_name = evi.name
            # If any of the args are *, keep the old entry
            if name == "*":
                name = evi.name
            if desc == "*":
                desc = evi.desc
            if image == "*":
                image = evi.image

            if client.area.evidence_mod == "HiddenCM":
                if self.correct_format(client, desc):
                    desc, pos, can_hide_in, show_in_dark = self.parse_desc(desc)
                else:
                    client.send_ooc(
                        'You entered a bad pos - evidence hidden! Make sure to have <owner=pos> at the top, where "pos" is the /pos this evidence should show up in. Put in "all" if you want it to show up in all pos, or "hidden" for no pos.'
                    )
                    pos = "hidden"
            self.evidences[id] = self.Evidence(name, desc, image, pos, can_hide_in, show_in_dark, evi.triggers)
            new_name = self.evidences[id].name
        else:
            # Are you serious? This is absolutely fucking mental.
            # Server sends evidence to client in an indexed list starting from 1.
            # Client sends evidence updates to server using an index starting from 0.
            # This needs a complete overhaul.
            id = client.evi_list[id + 1] - 1
            if id not in range(len(self.evidences)):
                return
            evi = self.evidences[id]
            # 0 - Do not show evidence in dark areas.
            if client.area.dark and evi.show_in_dark == 0:
                return
            # 2 - ONLY show evidence in dark areas. Will be hidden in non-dark areas.
            if not client.area.dark and evi.show_in_dark == 2:
                return
            old_name = evi.name
            # If any of the args are *, keep the old entry
            if name == "*":
                name = evi.name
            if desc == "*":
                desc = evi.desc
            if image == "*":
                image = evi.image
            self.evidences[id] = self.Evidence(
                name, desc, image, evi.pos, evi.can_hide_in, evi.show_in_dark, evi.triggers
            )
            new_name = evi.name

        namechange = f"'{old_name}' to '{new_name}'" if new_name != old_name else f"'{old_name}'"
        # Inform the CMs of evidence manupulation
        client.area.send_owner_command(
            "CT",
            client.server.config["hostname"],
            f"[{client.id}] {client.showname} edited evidence {id + 1}: {namechange} in area [{client.area.id}] {client.area.name}.",
            "1",
        )
        # send_owner_command does not tell CMs present in the area about evidence manipulation, so let's do that manually
        for c in client.area.owners:
            if c in client.area.clients:
                c.send_command(
                    "CT",
                    client.server.config["hostname"],
                    f"[{client.id}] {client.showname} edited evidence {id + 1}: {namechange} in this area.",
                    "1",
                )
