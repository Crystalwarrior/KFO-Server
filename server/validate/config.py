# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-21 Chrezm/Iuvee <thechrezm@gmail.com>
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

from typing import Dict, Any

import sys
if r'../..' not in sys.path:
    sys.path.append(r'../..')

from server.exceptions import ServerError
from server.validate_assets import Validate


class ValidateConfig(Validate):
    def validate_contents(self, contents, extra_parameters=None) -> Dict[str, Any]:
        # Check characters contents is indeed a list of strings
        if not isinstance(contents, dict):
            msg = (f'Expected the configurations to be a dictionary, found a '
                   f'{type(contents).__name__}: {contents}.')
            raise ServerError.FileSyntaxError(msg)

        # Check mandatory fields are defined
        mandatory_fields = [
            'playerlimit',
            'port',
            'timeout',
            'local',

            'use_masterserver',
            'masterserver_name',
            'masterserver_description',
            'masterserver_ip',
            'masterserver_port',

            'announce_areas',
            'motd',
            'hostname',

            'rp_mode_enabled',
            ]

        for field in mandatory_fields:
            if field not in contents:
                err = (f'Expected mandatory field "{field}" be defined in the configuration file, '
                       f'found it was not. Please make sure it is set and try again.')
                raise ServerError.FileSyntaxError(err)

        # Check mandatory passwords are defined
        mandatory_passwords = ['modpass', 'cmpass', 'gmpass']
        for password in mandatory_passwords:
            if password not in contents or not contents[password]:
                err = (f'Expected password "{password}" to be defined in the configuration file, '
                       f'found it was not. Please make sure it is set and try again.')
                raise ServerError.FileSyntaxError(err)
            else:
                contents[password] = str(contents[password])

        # Daily passwords are handled differently. They may optionally be not available.
        # What this means is the server does not want a daily password for that day
        # However, deliberately left empty passwords should still raise an error.
        optional_passwords = [f'gmpass{i}' for i in range(1, 8)]
        for password in optional_passwords:
            if password not in contents or not contents[password]:
                contents[password] = None
            else:
                contents[password] = str(contents[password])

        # Check that all passwords were generated are unique
        passwords = [
            'modpass',
            'cmpass',
            'gmpass',
            'gmpass1',
            'gmpass2',
            'gmpass3',
            'gmpass4',
            'gmpass5',
            'gmpass6',
            'gmpass7'
            ]

        for (i, password1) in enumerate(passwords):
            if contents[password1] is None:
                continue
            for (j, password2) in enumerate(passwords):
                if i == j:
                    continue
                if contents[password1] == contents[password2]:
                    err = (f'Expected all passwords in the configuration file to be different, '
                           f'found passwords "{password1}" and "{password2}" matched. '
                           f'Please change them so they are different and try again.')
                    raise ServerError.FileSyntaxError(err)

        # Type checking
        expected_types = {
            'playerlimit': int,
            'port': int,
            'timeout': (float, int),
            'local': bool,
            'show_ms2-prober': bool,

            'use_masterserver': bool,
            'masterserver_name': str,
            'masterserver_description': str,
            'masterserver_ip': str,
            'masterserver_port': int,

            'announce_areas': bool,
            'motd': str,
            'hostname': str,
            'discord_link': object,
            'utc_offset': object,

            'max_numdice': int,
            'max_numfaces': int,
            'max_modifier_length': int,
            'max_acceptable_term': (float, int),
            'def_numdice': int,
            'def_numfaces': int,
            'def_modifier': str,

            'rp_mode_enabled': bool,
            'blackout_background': str,
            'default_area_description': str,
            'party_lights_timeout': (float, int),
            'showname_max_length': int,
            'sneak_handicap': (float, int),
            'spectator_name': str,

            'music_change_floodguard': dict,
            }

        for (field_name, field_type) in expected_types.items():
            if field_name not in contents:
                continue
            if not isinstance(contents[field_name], field_type):
                msg = (f'Expected field "{field_name}" to be of type {field_type.__name__}, '
                       f'found it was a {type(contents[field_name]).__name__}.')
                raise ServerError.FileSyntaxError(msg)

        music_floodguard_types = {
            'times_per_interval': int,
            'interval_length': (float, int),
            'mute_length': (float, int),
            }

        for (field_name, field_type) in music_floodguard_types.items():
            if not isinstance(contents['music_change_floodguard'][field_name], field_type):
                msg = (f'Expected subfield "{field_name}" of music_change_floodguard to be of type '
                       f'{field_type.__name__}, found it was a '
                       f'{type(contents["music_change_floodguard"][field_name]).__name__}.')
                raise ServerError.FileSyntaxError(msg)

        # Nonnegative number check
        nonnegative_number_fields = {
            'playerlimit',
            'port',
            'timeout',

            'masterserver_port',

            'max_numdice',
            'max_numfaces',
            'max_modifier_length',
            'max_acceptable_term',
            'def_numdice',
            'def_numfaces',

            'party_lights_timeout',
            'showname_max_length',
            'sneak_handicap',
            }

        for field_name in nonnegative_number_fields:
            if field_name not in contents:
                continue
            if contents[field_name] < 0:
                msg = (f'Expected field "{field_name}" to be a nonnegative number, found it was '
                       f'not: {contents[field_name]}')
                raise ServerError.FileSyntaxError(msg)

        nonnegative_floodguard_fields = {
            'times_per_interval',
            'interval_length',
            'mute_length',
            }

        for field_name in nonnegative_floodguard_fields:
            if contents['music_change_floodguard'][field_name] < 0:
                msg = (f'Expected subfield "{field_name}" of music_change_floodguard to be a '
                       f'nonnegative number, found it was not: '
                       f'{contents["music_change_floodguard"][field_name]}')
                raise ServerError.FileSyntaxError(msg)

        return contents


if __name__ == '__main__':
    ValidateConfig().read_sysargv_and_validate(default='config.yaml')
