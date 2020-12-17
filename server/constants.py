# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-19 Chrezm/Iuvee <thechrezm@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import random
import re
import time
import warnings
import yaml

from enum import Enum
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

class ArgType(Enum):
    STR = 1
    STR_OR_EMPTY = 2
    INT = 3

class TargetType(Enum):
    #possible keys: ip, OOC, id, cname, ipid, hdid, showname, charfolder (for iniediting)
    IP = 0
    OOC_NAME = 1
    ID = 2
    CHAR_NAME = 3
    IPID = 4
    HDID = 5
    SHOWNAME = 6
    CHAR_FOLDER = 7
    ALL = 8

class Effects(Enum):
    B = ('Blindness', 'blinded', lambda client, value: client.change_blindness(value))
    D = ('Deafness', 'deafened', lambda client, value: client.change_deafened(value))
    G = ('Gagged', 'gagged', lambda client, value: client.change_gagged(value))

    @property
    def name(self):
        return self.value[0]

    @property
    def action(self):
        return self.value[1]

    @property
    def function(self):
        return self.value[2]

    @property
    def async_name(self):
        return 'as_effect_{}'.format(self.name.lower())

class Clients():
    class ClientDRO1d0d0(Enum):
        MS_INBOUND = [
            ('msg_type', ArgType.STR),  # 0
            ('pre', ArgType.STR_OR_EMPTY),  # 1
            ('folder', ArgType.STR),  # 2
            ('anim', ArgType.STR),  # 3
            ('text', ArgType.STR),  # 4
            ('pos', ArgType.STR),  # 5
            ('sfx', ArgType.STR),  # 6
            ('anim_type', ArgType.INT),  # 7
            ('cid', ArgType.INT),  # 8
            ('sfx_delay', ArgType.INT),  # 9
            ('button', ArgType.INT),  # 10
            ('evidence', ArgType.INT),  # 11
            ('flip', ArgType.INT),  # 12
            ('ding', ArgType.INT),  # 13
            ('color', ArgType.INT),  # 14
            ]

        MS_OUTBOUND = [
            ('msg_type', 0),  # 0
            ('pre', '-'),  # 1
            ('folder', '<NOCHAR>'),  # 2
            ('anim', '../../misc/blank'),  # 3
            ('msg', ''),  # 4
            ('pos', 'jud'),  # 5
            ('sfx', 0),  # 6
            ('anim_type', 0),  # 7
            ('cid', -1),  # 8
            ('sfx_delay', 0),  # 9
            ('button', 0),  # 10
            ('evidence', 0),  # 11
            ('flip', 0),  # 12
            ('ding', -1),  # 13
            ('color', 0),  # 14
            ('showname', ' '),  # 15
            ]

        MC_INBOUND = [
            ('name', ArgType.STR),  # 0
            ('cid', ArgType.INT),  # 1
            ]

        MC_OUTBOUND = [
            ('name', ''),  # 0
            ('cid', -1),  # 1
            ('showname', ''),  # 2
            ]

        BN_OUTBOUND = [
            ('name', ''),  # 0
            ]

    class ClientDROLegacy(Enum):
        MS_INBOUND = [
            ('msg_type', ArgType.STR), #0
            ('pre', ArgType.STR_OR_EMPTY), #1
            ('folder', ArgType.STR), #2
            ('anim', ArgType.STR), #3
            ('text', ArgType.STR), #4
            ('pos', ArgType.STR), #5
            ('sfx', ArgType.STR), #6
            ('anim_type', ArgType.INT), #7
            ('cid', ArgType.INT), #8
            ('sfx_delay', ArgType.INT), #9
            ('button', ArgType.INT), #10
            ('evidence', ArgType.INT), #11
            ('flip', ArgType.INT), #12
            ('ding', ArgType.INT), #13
            ('color', ArgType.INT), #14
            ]

        MS_OUTBOUND = [
            ('msg_type', 0), #0
            ('pre', '-'), #1
            ('folder', '<NOCHAR>'), #2
            ('anim', '../../misc/blank'), #3
            ('msg', ''), #4
            ('pos', 'jud'), #5
            ('sfx', 0), #6
            ('anim_type', 0), #7
            ('cid', 0), #8
            ('sfx_delay', 0), #9
            ('button', 0), #10
            ('evidence', 0), #11
            ('flip', 0), #12
            ('ding', -1), #13
            ('color', 0), #14
            ('showname', ' '), #15
            ]

        MC_INBOUND = [
            ('name', ArgType.STR), #0
            ('cid', ArgType.INT), #1
            ]

        MC_OUTBOUND = [
            ('name', ''), #0
            ('cid', -1), #1
            ]

        BN_OUTBOUND = [
            ('name', ''), #0
            ]

    class ClientAO2d6(Enum):
        MS_INBOUND = [
            ('msg_type', ArgType.STR), #0
            ('pre', ArgType.STR_OR_EMPTY), #1
            ('folder', ArgType.STR), #2
            ('anim', ArgType.STR), #3
            ('text', ArgType.STR), #4
            ('pos', ArgType.STR), #5
            ('sfx', ArgType.STR), #6
            ('anim_type', ArgType.INT), #7
            ('cid', ArgType.INT), #8
            ('sfx_delay', ArgType.INT), #9
            ('button', ArgType.INT), #10
            ('evidence', ArgType.INT), #11
            ('flip', ArgType.INT), #12
            ('ding', ArgType.INT), #13
            ('color', ArgType.INT), #14
            ('showname', ArgType.STR_OR_EMPTY), #15
            ('charid_pair', ArgType.INT), #16
            ('offset_pair', ArgType.INT), #17
            ('nonint_pre', ArgType.INT), #18
            ]

        MS_OUTBOUND = [
            ('msg_type', 0), #0
            ('pre', '-'), #1
            ('folder', '<NOCHAR>'), #2
            ('anim', '../../misc/blank'), #3
            ('msg', ''), #4
            ('pos', 'jud'), #5
            ('sfx', 0), #6
            ('anim_type', 0), #7
            ('cid', 0), #8
            ('sfx_delay', 0), #9
            ('button', 0), #10
            ('evidence', 0), #11
            ('flip', 0), #12
            ('ding', -1), #13
            ('color', 0), #14
            ('showname', ' '), #15
            ('charid_pair', -1), #16
            ('other_folder', ''), #17
            ('other_emote', ''), #18
            ('offset_pair', 0), #19
            ('other_offset', 0), #20
            ('other_flip', 0), #21
            ('nonint_pre', 0), #22
            ]

        MC_INBOUND = [
            ('name', ArgType.STR), #0
            ('cid', ArgType.INT), #1
            ('showname', ArgType.STR_OR_EMPTY), #2
            ]

        MC_OUTBOUND = [
            ('name', ''), #0
            ('cid', -1), #1
            ('showname', ''), #2
            ]

        BN_OUTBOUND = [
            ('name', ''), #0
            ]

    class ClientAO2d7(Enum):
        MS_INBOUND = [
            ('msg_type', ArgType.STR), #0
            ('pre', ArgType.STR_OR_EMPTY), #1
            ('folder', ArgType.STR), #2
            ('anim', ArgType.STR), #3
            ('text', ArgType.STR), #4
            ('pos', ArgType.STR), #5
            ('sfx', ArgType.STR), #6
            ('anim_type', ArgType.INT), #7
            ('cid', ArgType.INT), #8
            ('sfx_delay', ArgType.INT), #9
            ('button', ArgType.INT), #10
            ('evidence', ArgType.INT), #11
            ('flip', ArgType.INT), #12
            ('ding', ArgType.INT), #13
            ('color', ArgType.INT), #14
            ('showname', ArgType.STR_OR_EMPTY), #15
            ('charid_pair', ArgType.INT), #16
            ('offset_pair', ArgType.INT), #17
            ('nonint_pre', ArgType.INT), #18
            ('looping_sfx', ArgType.INT), #19
            ('screenshake', ArgType.INT), #20
            ('frame_screenshake', ArgType.STR_OR_EMPTY), #21
            ('frame_realization', ArgType.STR_OR_EMPTY), #22
            ('frame_sfx', ArgType.STR_OR_EMPTY), #23
            ]

        MS_OUTBOUND = [
            ('msg_type', 0), #0
            ('pre', '-'), #1
            ('folder', '<NOCHAR>'), #2
            ('anim', '../../misc/blank'), #3
            ('msg', ''), #4
            ('pos', 'jud'), #5
            ('sfx', 0), #6
            ('anim_type', 0), #7
            ('cid', 0), #8
            ('sfx_delay', 0), #9
            ('button', 0), #10
            ('evidence', 0), #11
            ('flip', 0), #12
            ('ding', -1), #13
            ('color', 0), #14
            ('showname', ' '), #15
            ('charid_pair', -1), #16
            ('other_folder', ''), #17
            ('other_emote', ''), #18
            ('offset_pair', 0), #19
            ('other_offset', 0), #20
            ('other_flip', 0), #21
            ('nonint_pre', 0), #22
            ('looping_sfx', 0), #23
            ('screenshake', 0), #24
            ('frame_screenshake', ''), #25
            ('frame_realization', ''), #26
            ('frame_sfx', ''), #27
            ]

        MC_INBOUND = [
            ('name', ArgType.STR), #0
            ('cid', ArgType.INT), #1
            ('showname', ArgType.STR_OR_EMPTY), #2
            ]

        MC_OUTBOUND = [
            ('name', ''), #0
            ('cid', -1), #1
            ('showname', ''), #2
            ]

        BN_OUTBOUND = [
            ('name', ''), #0
            ]

    class ClientAO2d8d4(Enum):
        MS_INBOUND = [
            ('msg_type', ArgType.STR), #0
            ('pre', ArgType.STR_OR_EMPTY), #1
            ('folder', ArgType.STR), #2
            ('anim', ArgType.STR), #3
            ('text', ArgType.STR), #4
            ('pos', ArgType.STR), #5
            ('sfx', ArgType.STR), #6
            ('anim_type', ArgType.INT), #7
            ('cid', ArgType.INT), #8
            ('sfx_delay', ArgType.INT), #9
            ('button', ArgType.INT), #10
            ('evidence', ArgType.INT), #11
            ('flip', ArgType.INT), #12
            ('ding', ArgType.INT), #13
            ('color', ArgType.INT), #14
            ('showname', ArgType.STR_OR_EMPTY), #15
            ('charid_pair_pair_order', ArgType.STR), #16
            ('offset_pair', ArgType.INT), #17
            ('nonint_pre', ArgType.INT), #18
            ('looping_sfx', ArgType.INT), #19
            ('screenshake', ArgType.INT), #20
            ('frame_screenshake', ArgType.STR_OR_EMPTY), #21
            ('frame_realization', ArgType.STR_OR_EMPTY), #22
            ('frame_sfx', ArgType.STR_OR_EMPTY), #23
            ('additive', ArgType.INT), #24
            ('effect', ArgType.STR), #25
            ]

        MS_OUTBOUND = [
            ('msg_type', 0), #0
            ('pre', '-'), #1
            ('folder', '<NOCHAR>'), #2
            ('anim', '../../misc/blank'), #3
            ('msg', ''), #4
            ('pos', 'jud'), #5
            ('sfx', 0), #6
            ('anim_type', 0), #7
            ('cid', 0), #8
            ('sfx_delay', 0), #9
            ('button', 0), #10
            ('evidence', 0), #11
            ('flip', 0), #12
            ('ding', -1), #13
            ('color', 0), #14
            ('showname', ' '), #15
            ('charid_pair_pair_order', -1), #16
            ('other_folder', ''), #17
            ('other_emote', ''), #18
            ('offset_pair', 0), #19
            ('other_offset', 0), #20
            ('other_flip', 0), #21
            ('nonint_pre', 0), #22
            ('looping_sfx', 0), #23
            ('screenshake', 0), #24
            ('frame_screenshake', ''), #25
            ('frame_realization', ''), #26
            ('frame_sfx', ''), #27
            ('additive', 0), #28
            ('effect', ''), #29
            ]

        MC_INBOUND = [
            ('name', ArgType.STR), #0
            ('cid', ArgType.INT), #1
            ('showname', ArgType.STR_OR_EMPTY), #2
            ('effects', ArgType.INT), #3
            ]

        MC_OUTBOUND = [
            ('name', ''), #0
            ('cid', -1), #1
            ('showname', ''), #2
            ('loop', -1), #3
            ('channel', 0), #4
            ('effects', 0), #5
            ]

        BN_OUTBOUND = [
            ('name', ''), #0
            ('pos', ''), #1
            ]

    ClientKFO2d8 = Enum('ClientKFO2d8', [(m.name, m.value) for m in ClientAO2d7])
    ClientCC22 = Enum('ClientCC22', [(m.name, m.value) for m in ClientAO2d6])
    ClientCC24 = Enum('ClientCC24', [(m.name, m.value) for m in ClientAO2d8d4])

class Constants():
    @staticmethod
    def fopen(file, *args, **kwargs):
        try:
            f = open(file, *args, **kwargs)
            return f
        except FileNotFoundError:
            info = 'File not found: {}'.format(file)
            raise ServerError(info, code="FileNotFound")
        except OSError as ex:
            raise ServerError(str(ex), code="OSError")

    @staticmethod
    def yaml_load(file):
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            # Extract the name of the yaml
            separator = max(file.name.rfind('\\'), file.name.rfind('/'))
            file_name = file.name[separator+1:]
            # Then raise the exception
            msg = ('File {} returned the following YAML error when loading: `{}`.'
                   .format(file_name, exc))
            raise ServerError.YAMLInvalidError(msg)

    @staticmethod
    def get_time():
        return time.asctime(time.localtime(time.time()))

    @staticmethod
    def get_time_iso():
        return time.strftime('[%Y-%m-%dT%H:%M:%S]')

    @staticmethod
    def time_remaining(start, length):
        current = time.time()
        remaining = start+length-current
        return remaining, Constants.time_format(remaining)

    @staticmethod
    def time_elapsed(start):
        current = time.time()
        return Constants.time_format(current-start)

    @staticmethod
    def time_format(length):
        if length < 10:
            text = "{} seconds".format('{0:.1f}'.format(length))
        elif length < 60:
            text = "{} seconds".format(int(length))
        elif length < 3600:
            text = "{}:{}".format(int(length//60),
                                  '{0:02d}'.format(int(length%60)))
        else:
            text = "{}:{}:{}".format(int(length//3600),
                                     '{0:02d}'.format(int((length%3600)//60)),
                                     '{0:02d}'.format(int(length%60)))
        return text

    @staticmethod
    def assert_command(client, arg, is_staff=None, is_officer=None, is_mod=None, parameters=None,
                       split_spaces=None, split_commas=False):
        if is_staff is not None:
            if is_staff is True and not client.is_staff():
                raise ClientError.UnauthorizedError('You must be authorized to do that.')
            if is_staff is False and client.is_staff():
                raise ClientError.UnauthorizedError('You have too high a rank to do that.')

        if is_officer is not None:
            if is_officer is True and not (client.is_mod or client.is_cm):
                raise ClientError.UnauthorizedError('You must be authorized to do that.')
            if is_officer is False and (client.is_mod or client.is_cm):
                raise ClientError.UnauthorizedError('You have too high a rank to do that.')

        if is_mod is not None:
            if is_mod is True and not client.is_mod:
                raise ClientError.UnauthorizedError('You must be authorized to do that.')
            if is_mod is False and client.is_mod():
                raise ClientError.UnauthorizedError('You have too high a rank to do that.')

        if parameters is not None:
            symbol, num = parameters[0], [int(i) for i in parameters[1:].split('-')]
            # Set up default values
            if (num[0] > 0 or symbol == '&') and split_spaces is None and split_commas is False:
                split_spaces = True
            elif split_spaces is None:
                split_spaces = False

            if split_spaces:
                arg = arg.split(' ')
            elif split_commas:
                arg = arg.split(', ')

            if arg == ['']:
                arg = list()

            error = None
            if symbol == '=':
                expect = num[0]
                if len(arg) != expect:
                    if expect == 0:
                        expect = 'no'
                    error = ('This command has {} argument{}.', expect)
            elif symbol == '<':
                expect = num[0] - 1
                if len(arg) > expect:
                    error = ('This command has at most {} argument{}.', expect)
            elif symbol == '>':
                expect = num[0] + 1
                if len(arg) < expect:
                    error = ('This command has at least {} argument{}.', expect)
            elif symbol == '&':
                expect = num
                if not expect[0] <= len(arg) <= expect[1]:
                    expect = '{} to {}'.format(expect[0], expect[1])
                    error = ('This command has from {} argument{}.', expect)

            if error:
                raise ArgumentError(error[0].format(error[1], 's' if error[1] != 1 else ''))

    @staticmethod
    def command_assert(client, arg, is_staff=None, is_mod=None, parameters=None,
                       split_spaces=None, split_commas=False):
        """
        Kept for backwards compatibility. Use assert_command.
        """
        message = ('Code is using old command_assert syntax. Please change it (or ask your server '
                   'developer) so that it uses Constants.assert_command instead.')
        warnings.warn(message, category=UserWarning, stacklevel=2)

        if is_staff is not None:
            if is_staff is True and not client.is_staff():
                raise ClientError.UnauthorizedError('You must be authorized to do that.')
            if is_staff is False and client.is_staff():
                raise ClientError.UnauthorizedError('You have too high a rank to do that.')

        if is_mod is not None:
            if is_mod is True and not client.is_mod:
                raise ClientError.UnauthorizedError('You must be authorized to do that.')
            if is_mod is False and client.is_mod():
                raise ClientError.UnauthorizedError('You have too high a rank to do that.')

        if parameters is not None:
            symbol, num = parameters[0], [int(i) for i in parameters[1:].split('-')]
            # Set up default values
            if (num[0] > 0 or symbol == '&') and split_spaces is None and split_commas is False:
                split_spaces = True
            elif split_spaces is None:
                split_spaces = False

            if split_spaces:
                arg = arg.split(' ')
            elif split_commas:
                arg = arg.split(', ')

            if arg == ['']:
                arg = list()

            error = None
            if symbol == '=':
                expect = num[0]
                if len(arg) != expect:
                    if expect == 0:
                        expect = 'no'
                    error = ('This command has {} argument{}.', expect)
            elif symbol == '<':
                expect = num[0] - 1
                if len(arg) > expect:
                    error = ('This command has at most {} argument{}.', expect)
            elif symbol == '>':
                expect = num[0] + 1
                if len(arg) < expect:
                    error = ('This command has at least {} argument{}.', expect)
            elif symbol == '&':
                expect = num
                if not expect[0] <= len(arg) <= expect[1]:
                    expect = '{} to {}'.format(expect[0], expect[1])
                    error = ('This command has from {} argument{}.', expect)

            if error:
                raise ArgumentError(error[0].format(error[1], 's' if error[1] != 1 else ''))

    @staticmethod
    def build_cond(sender, is_staff=None, is_officer=None, is_mod=None, in_area=None, pred=None,
                   part_of=None, not_to=None, to_blind=None, to_deaf=None, is_zstaff=None,
                   is_zstaff_flex=None):
        """
        Acceptable conditions:
            is_staff: If target is GM, CM or Mod
            is_officer: If target is CM or Mod
            is_mod: If target is Mod
            in_area: If target is in client's area, or some particular area
            part_of: If target is an element of this set
            not_to: If target is not in a set of clients that are filtered out
            to_blind: If target is blind
            to_deaf: If target is deaf
            is_zstaff: If target is GM, CM or Mod, and if they are watching the zone the sender's
             area is in, or the area that is given. This EXPECTS the targets to be watching a
             non-None zone.
            is_zstaff_flex: If target is GM, CM, or Mod, and if they are watching the zone the
             sender's area is in, or the area that is given, or both the target's watched zone
             and the zone the sender's/given area is in are both None for its True and area cases.
            pred: If target satisfies some custom condition
        """
        conditions = list()

        if is_staff is True:
            conditions.append(lambda c: c.is_staff())
        elif is_staff is False:
            conditions.append(lambda c: not c.is_staff())
        elif is_staff is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond is_staff: {}'.format(is_staff))

        if is_officer is True:
            conditions.append(lambda c: c.is_cm or c.is_mod)
        elif is_officer is False:
            conditions.append(lambda c: not (c.is_cm or c.is_mod))
        elif is_officer is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond is_officer: {}'.format(is_officer))

        if is_mod is True:
            conditions.append(lambda c: c.is_mod)
        elif is_mod is False:
            conditions.append(lambda c: not c.is_mod)
        elif is_mod is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond is_mod: {}'.format(is_mod))

        if in_area is True:
            conditions.append(lambda c: c.area == sender.area)
        elif in_area is False:
            conditions.append(lambda c: c.area != sender.area)
        elif isinstance(in_area, type(sender.area)): # Lazy way of finding if in_area is an area obj
            conditions.append(lambda c: c.area == in_area)
        elif isinstance(in_area, set):
            conditions.append(lambda c: c.area in in_area)
        elif in_area is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond in_area: {}'.format(in_area))

        if part_of is not None:
            conditions.append(lambda c: c in part_of)

        if not_to is not None:
            conditions.append(lambda c: c not in not_to)

        if to_blind is True:
            conditions.append(lambda c: c.is_blind)
        elif to_blind is False:
            conditions.append(lambda c: not c.is_blind)
        elif to_blind is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond to_blind: {}'.format(to_blind))

        if to_deaf is True:
            conditions.append(lambda c: c.is_deaf)
        elif to_deaf is False:
            conditions.append(lambda c: not c.is_deaf)
        elif to_deaf is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond to_deaf: {}'.format(to_deaf))

        # This is a strict parameter.
        # To be precise, is_zstaff expects the sender to be watching a zone or be in a zone, or
        # if given an area, that it is part of a zone.
        if is_zstaff is True:
            # Only staff members who are watching the sender's zone will receive it, PROVIDED that
            # the sender is watching a zone, or in an area part of a zone. If neither is true,
            # NO notification is sent.
            conditions.append(lambda c: c.is_staff() and c.zone_watched)
            if sender.zone_watched:
                conditions.append(lambda c: (c.zone_watched == sender.zone_watched))
            elif sender.area.in_zone:
                conditions.append(lambda c: (c.zone_watched == sender.area.in_zone))
            else:
                conditions.append(lambda c: False)
        elif is_zstaff is False:
            if sender.zone_watched:
                conditions.append(lambda c: (c.zone_watched != sender.zone_watched))
            elif sender.area.in_zone:
                conditions.append(lambda c: (c.zone_watched != sender.area.in_zone))
            else:
                conditions.append(lambda c: False)
        elif isinstance(is_zstaff, sender.server.area_manager.Area):
            # Only staff members who are watching the area's zone will receive it, PROVIDED the area
            # is part of a zone. Otherwise, NO notification is sent.
            target_zone = is_zstaff.in_zone
            if target_zone:
                conditions.append(lambda c: c.is_staff() and c.zone_watched == target_zone)
            else:
                conditions.append(lambda c: False)
        elif is_zstaff is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond is_zstaff: {}'.format(is_zstaff))

        # This is a less strict parameter. The sender may or may not be in a zone (or the given
        # area may not be in a zone), in which case it will ignore zone limitations and effectively
        # just act as is_staff.
        # This is a BACKWARDS COMPATIBILITY only parameter, designed to keep the pre-4.2 notifs
        # that were sent to all staff members as they were pre-zones, so that if a notif happens
        # outside a zone, it notifies all staff members
        # Please use is_zstaff for 4.2 forwards.
        if is_zstaff_flex is True:
            # Only staff members who are watching the sender's zone will receive it, PROVIDED that
            # the sender is watching a zone, or in an area part of a zone. If neither is true,
            # NO notification is sent.
            conditions.append(lambda c: c.is_staff())
            if sender.zone_watched:
                conditions.append(lambda c: (c.zone_watched == sender.zone_watched))
            elif sender.area.in_zone:
                conditions.append(lambda c: (c.zone_watched == sender.area.in_zone))
        elif is_zstaff_flex is False:
            if sender.zone_watched:
                condition1 = lambda c: (c.zone_watched != sender.zone_watched)
            elif sender.area.in_zone:
                condition1 = lambda c: (c.zone_watched != sender.area.in_zone)
            else:
                condition1 = lambda c: False
            conditions.append(lambda c: condition1(c) or not c.is_staff())
        elif isinstance(is_zstaff_flex, sender.server.area_manager.Area):
            # Only staff members who are watching the area's zone will receive it, PROVIDED the area
            # is part of a zone. Otherwise, NO notification is sent.
            target_zone = is_zstaff_flex.in_zone
            conditions.append(lambda c: c.is_staff() and c.zone_watched == target_zone)
        elif is_zstaff_flex is None:
            pass
        else:
            raise KeyError('Invalid argument for build_cond is_zstaff_flex: {}'
                           .format(is_zstaff_flex))

        if pred is not None:
            conditions.append(pred)

        cond = lambda c: all([cond(c) for cond in conditions])

        return cond

    @staticmethod
    def dice_roll(arg, command_type, server):
        """
        Calculate roll results.
        Confront /roll documentation for more details.
        """

        max_numdice = server.config['max_numdice']
        max_numfaces = server.config['max_numfaces']
        max_modifier_length = server.config['max_modifier_length']
        max_acceptable_term = server.config['max_acceptable_term']
        def_numdice = server.config['def_numdice']
        def_numfaces = server.config['def_numfaces']
        def_modifier = server.config['def_modifier']

        ACCEPTABLE_IN_MODIFIER = '1234567890+-*/().r'
        MAXDIVZERO_ATTEMPTS = 10

        special_calculation = False # Is it given a modifier? False until proven otherwise
        args = arg.split(' ')
        arg_length = len(args)

        # Parse number of dice, number of faces and modifiers
        if arg:
            if arg_length == 2:
                dice_type, modifiers = args
                if len(modifiers) > max_modifier_length:
                    raise ArgumentError('The modifier is too long to compute. Please try a shorter '
                                        'one.')
            elif arg_length == 1:
                dice_type, modifiers = arg, ''
            else:
                raise ArgumentError('This command takes one or two arguments. Use /{} '
                                    '<num_dice>d<num_faces> <modifiers>'.format(command_type))

            dice_type = dice_type.split('d')
            if len(dice_type) == 1:
                dice_type.insert(0, 1)
            if dice_type[0] == '':
                dice_type[0] = '1'

            try:
                num_dice, num_faces = int(dice_type[0]), int(dice_type[1])
            except ValueError:
                raise ArgumentError('The number of rolls and faces of the dice must be '
                                    'positive integers.')

            if not 1 <= num_dice <= max_numdice:
                raise ArgumentError('Number of rolls must be between 1 and {}.'.format(max_numdice))
            if not 1 <= num_faces <= max_numfaces:
                raise ArgumentError('Number of faces must be between 1 and {}.'
                                    .format(max_numfaces))

            for char in modifiers:
                if char not in ACCEPTABLE_IN_MODIFIER:
                    raise ArgumentError('The modifier must only include numbers and standard '
                                        'mathematical operations in the modifier.')
                if char == 'r':
                    special_calculation = True
            if '**' in modifiers: #Exponentiation manually disabled, it can be pretty dangerous
                raise ArgumentError('The modifier must only include numbers and standard '
                                    'mathematical operations in the modifier.')
        else:
            # Default
            num_dice, num_faces, modifiers = def_numdice, def_numfaces, def_modifier

        roll = ''

        for _ in range(num_dice):
            divzero_attempts = 0
            while True: # Roll until no division by zeroes happen (or it gives up)
                # raw_roll: original roll
                # mid_roll: result after modifiers (if any) have been applied to original roll
                # final_roll: result after previous result was capped between 1 and max_numfaces

                raw_roll = str(server.random.randint(1, num_faces))
                if modifiers == '':
                    aux_modifier = ''
                    mid_roll = int(raw_roll)
                else:
                    if special_calculation: # Ex: /roll 20 3*r+1
                        aux_modifier = modifiers.replace('r', raw_roll) + '='
                    elif modifiers[0].isdigit(): # Ex /roll 20 3
                        aux_modifier = raw_roll + "+" + modifiers + '='
                    else: # Ex /roll 20 -3
                        aux_modifier = raw_roll + modifiers + '='

                    # Prevent any terms from reaching past max_acceptable_term in order to prevent
                    # server lag due to potentially frivolous dice rolls
                    # In order to do that, it will split the string by the numbers it uses
                    # and check if any individual number is larger than said term.
                    # This also doubles as a second-line defense to junk entries such as "+1..4"
                    aux = aux_modifier[:-1]
                    for j in "+-*/()":
                        aux = aux.replace(j, "!")
                    aux = aux.split('!')
                    for j in aux:
                        try:
                            if j != '' and round(float(j)) > max_acceptable_term:
                                raise ArgumentError('The modifier must take numbers within the '
                                                    'computation limit of the server.')
                        except ValueError:
                            raise ArgumentError('The modifier has a syntax error.')

                    for j in range(10):
                        # Deals with inputs like 3(r-1), which act like Python functions.
                        # Needed to be done here to prevent Python 3.8 from raising SyntaxWarning
                        if '{}('.format(j) in aux_modifier[:-1]:
                            raise ArgumentError('The modifier has a syntax error.')

                    try:
                        # By this point it should be 'safe' to run eval
                        mid_roll = round(eval(aux_modifier[:-1]))
                    except SyntaxError:
                        raise ArgumentError('The modifier has a syntax error.')
                    except ZeroDivisionError:
                        divzero_attempts += 1
                        if divzero_attempts == MAXDIVZERO_ATTEMPTS:
                            raise ArgumentError('The modifier causes divisions by zero too often.')
                        continue
                break

            final_roll = min(max_acceptable_term, max(1, mid_roll))

            # Build output string
            if final_roll != mid_roll:
                # This visually indicates the roll was capped off due to exceeding the
                # acceptable roll range
                final_roll = "|" + str(final_roll)
            else:
                final_roll = str(final_roll)

            if modifiers != '':
                roll += str(raw_roll + ':')
            roll += str(aux_modifier + final_roll) + ', '

        roll = roll[:-2] # Remove last ', '
        if num_dice > 1:
            roll = '(' + roll + ')'

        return roll, num_faces

    @staticmethod
    def disemvowel_message(message):
        return Constants.remove_letters(message, 'aeiou')

    @staticmethod
    def disemconsonant_message(message):
        return Constants.remove_letters(message, 'bcdfghjklmnpqrstvwxyz')

    @staticmethod
    def fix_and_setify(csv_values):
        """
        For the area parameters that include lists of comma-separated values, parse them
        appropiately before turning them into sets.
        """

        l = csv_values.split(', ')
        for i in range(len(l)): #Ah, escape characters... again...
            l[i] = l[i].replace(',\\', ',')

        if l in [list(), ['']]:
            return set()
        return set(l)

    @staticmethod
    def gimp_message():
        message = ['ERP IS BAN',
                   'I\'m fucking gimped because I\'m both autistic and a retard!',
                   'HELP ME',
                   'Boy, I sure do love Dia, the best admin, and the cutest!!!!!',
                   'I\'M SEVERELY AUTISTIC!!!!',
                   '[PEES FREELY]',
                   'KILL ME',
                   'I found this place on reddit XD',
                   '(((((case????)))))',
                   'Anyone else a fan of MLP?',
                   'does this server have sans from undertale?',
                   'what does call mod do',
                   'does anyone have a miiverse account?',
                   'Drop me a PM if you want to ERP',
                   'Join my discord server please',
                   'can I have mod pls?',
                   'why is everyone a missingo?',
                   'how 2 change areas?',
                   'does anyone want to check out my tumblr? :3',
                   '19 years of perfection, i don\'t play games to fucking lose',
                   'nah... your taunts are fucking useless... only defeat angers me... by trying '
                   'to taunt just earns you my pitty',
                   'When do we remove dangits',
                   'MODS STOP GIMPING ME',
                   'Please don\'t say things like ni**er and f**k it\'s very rude and I don\'t '
                   'like it',
                   'PLAY NORMIES PLS']
        return random.choice(message)

    @staticmethod
    def gagged_message():
        length = random.randint(5, 9)
        letters = ['g', 'h', 'm', 'r']
        starters = ['G', 'M']
        message = random.choice(starters) + "".join([random.choice(letters) for _ in range(length)])
        return message

    @staticmethod
    def cjoin(structure, the=False, sort=True):
        connector = 'the ' if the else ''
        new_structure = sorted(structure) if sort else list(structure)

        info = '{}{}'.format(connector, new_structure[0])
        if len(new_structure) > 1:
            for i in range(1, len(new_structure)-1):
                info += ', {}{}'.format(connector, new_structure[i])
            info += ' and {}{}'.format(connector, new_structure[-1])
        return info

    @staticmethod
    def parse_area_names(client, areas):
        """
        Convert a list of area names or IDs into area objects.
        """

        area_list = list()
        # Replace arguments with proper area objects
        for i in range(len(areas)):
            # The escape character combination for areas that have commas in their name is ',\'
            # (yes, I know it's inverted)
            # This double try block takes into account the possibility that some weird person
            # wants ',\' as part of their actual area name. If you are that person... just... why
            try:
                target = areas[i].replace(',\\', ',')
                area_list.append(client.server.area_manager.get_area_by_name(target))
            except AreaError:
                try:
                    area_list.append(client.server.area_manager.get_area_by_name(areas[i]))
                except AreaError:
                    try:
                        area_list.append(client.server.area_manager.get_area_by_id(int(areas[i])))
                    except Exception:
                        raise ArgumentError('Could not parse area `{}`.'.format(areas[i]))
        return area_list

    @staticmethod
    def parse_effects(client, effects):
        """
        Convert a sequence of characters to their associated effect names.
        """

        if not effects:
            raise ArgumentError('Expected effects.')
        if len({x.lower() for x in effects}) != len([x.lower() for x in effects]):
            raise ArgumentError('Effect list cannot contained repeated characters.')

        parsed_effects = set()
        for effect_letter in effects:
            try:
                parsed_effects.add(Effects[effect_letter.capitalize()])
            except KeyError:
                raise ArgumentError('Invalid effect letter `{}`.'.format(effect_letter))

        return parsed_effects

    @staticmethod
    def parse_id(client, identifier):
        """
        Given a client ID, returns the client that matches this identifier.
        """

        if identifier == '':
            raise ArgumentError('Expected client ID.')
        if not identifier.isdigit():
            raise ArgumentError('`{}` does not look like a valid client ID.'.format(identifier))

        targets = client.server.client_manager.get_targets(client, TargetType.ID,
                                                           int(identifier), False)

        if not targets:
            raise ClientError('No targets found.')

        return targets[0]

    @staticmethod
    def parse_id_or_ipid(client, identifier):
        """
        Given either a client ID or IPID, returns all clients that match this identifier.

        First tries to match by ID, then by IPID. IPID can be of the same length as client ID and
        thus be mismatched, but it is extremely unlikely (1 in 100,000,000 chance).
        """

        if identifier == '':
            raise ArgumentError('Expected client ID or IPID.')
        if not identifier.isdigit() or len(identifier) > 10:
            raise ArgumentError('{} does not look like a valid client ID or IPID.'
                                .format(identifier))

        idnt = int(identifier)
        # First try and match by ID
        targets = client.server.client_manager.get_targets(client, TargetType.ID, idnt, False)
        if targets:
            return targets

        # Otherwise, try and match by IPID
        # PROVIDED the client is CM or mod
        if client.is_cm or client.is_mod:
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, idnt, False)
            if targets:
                return targets

        raise ArgumentError('No targets found.')

    @staticmethod
    def parse_passage_lock(client, areas, bilock=False):
        now_reachable = []
        num_areas = 2 if bilock else 1

        # First check if it is the case a non-authorized use is trying to change passages to areas
        # that do not allow their passages to be modified
        for i in range(num_areas):
            if not areas[i].change_reachability_allowed and not client.is_staff():
                raise ClientError('You must be authorized to change passages in area {}.'
                                  .format(areas[i].name))

        # Just in case something goes wrong, have a backup to revert back
        formerly_reachable = [areas[i].reachable_areas for i in range(num_areas)]

        for i in range(num_areas):
            reachable = areas[i].reachable_areas
            now_reachable.append(False)

            if reachable == {'<ALL>'}: # Case removing a passage from an area connected to all areas
                reachable = client.server.area_manager.area_names - {areas[1-i].name}
            elif areas[1-i].name in reachable: # Case removing a passage
                reachable = reachable - {areas[1-i].name}
            else: # Case creating a passage
                # Make sure that non-authorized users cannot create passages did not exist before
                if not (client.is_staff() or areas[1-i].name in areas[i].staffset_reachable_areas or
                        areas[i].staffset_reachable_areas == {'<ALL>'}):
                    # And if they try and do, undo changes and restore formerly reachable areas
                    for j in range(num_areas):
                        areas[j].reachable_areas = formerly_reachable[j]
                    raise ClientError('You must be authorized to create a new passage from {} to '
                                      '{}.'.format(areas[i].name, areas[1-i].name))

                # Otherise, create new passages
                reachable.add(areas[1-i].name)
                now_reachable[i] = True

            areas[i].reachable_areas = reachable
            if client.is_staff():
                areas[i].staffset_reachable_areas = reachable

        return now_reachable

    @staticmethod
    def parse_time_length(time_length):
        """
        Convert seconds into a formatted string representing timelength.
        """
        TIMER_LIMIT = 21600 # 6 hours in seconds
        # Check if valid length and convert to seconds
        raw_length = time_length.split(':')
        try:
            length = [int(entry) for entry in raw_length]
        except ValueError:
            raise ClientError('Expected length of time.')

        if len(length) == 1:
            length = length[0]
        elif len(length) == 2:
            length = length[0]*60 + length[1]
        elif len(length) == 3:
            length = length[0]*3600 + length[1]*60 + length[2]
        else:
            raise ClientError('Expected length of time.')

        if length > TIMER_LIMIT:
            raise ClientError('Suggested timer length exceeds server limit.')
        if length <= 0:
            raise ClientError('Expected positive time length.')
        return length

    @staticmethod
    def parse_two_area_names(client, raw_areas, area_duplicate=True, check_valid_range=True):
        """
        Convert the area passage commands inputs into inputs for parse_area_names.
        and check for the different cases it needs to possibly handle
        """

        # Convert to two-area situation
        if len(raw_areas) == 0:
            raw_areas = [client.area.name, client.area.name]
        elif len(raw_areas) == 1:
            if area_duplicate:
                raw_areas.append(raw_areas[0])
            else:
                raw_areas.insert(0, client.area.name)
        elif len(raw_areas) > 2:
            raise ArgumentError('Expected at most two area names.')

        # Replace arguments with proper area objects
        areas = Constants.parse_area_names(client, raw_areas)

        if check_valid_range and areas[0].id > areas[1].id:
            raise ArgumentError('The ID of the first area must be lower than the ID of the second '
                                'area.')
        if not area_duplicate and areas[0].id == areas[1].id:
            raise ArgumentError('Areas must be different.')

        return areas

    @staticmethod
    def remove_h_message(message):
        return Constants.remove_letters(message, 'h')

    @staticmethod
    def remove_letters(message, target):
        message = re.sub("[{}]".format(target), "", message, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", message)

    @staticmethod
    def format_area_ranges(areas) -> str:
        # Obtain area ranges from an iterable containing area objects
        # Ex. If areas contains area 1, 2, 3, 5, 6 and 8, this will return "1-3, 5-6 and 8"
        # If areas is None or empty, returns None
        if not areas:
            return 'None'

        raw_area_ids = sorted([area.id for area in areas])
        last_area = raw_area_ids[0]
        area_ranges = list()
        current_range = [last_area, last_area]

        def add_range():
            if current_range[0] != current_range[1]:
                area_ranges.append('{}-{}'.format(current_range[0], current_range[1]))
            else:
                area_ranges.append('{}'.format(current_range[0]))

        for area_id in raw_area_ids[1:]:
            if area_id != last_area+1:
                add_range()
                current_range = [area_id, area_id]
            else:
                current_range[1] = area_id
            last_area = area_id

        add_range()
        return Constants.cjoin(area_ranges)

    @staticmethod
    def contains_illegal_characters(text) -> bool:
        """
        Returns True if `text` contains a zero-width character, False otherwise.
        Parameters
        ----------
        text : str
            Text to check.
        Returns
        -------
        bool
            True if `text` contains a zero-width character, False otherwise.
        """

        illegal_characters = [
            '\u200b',
            '\u200c',
            '\u200d',
            '\u2060',
            '\ufeff',
            ]

        for char in illegal_characters:
            if char in text:
                return True
        return False
