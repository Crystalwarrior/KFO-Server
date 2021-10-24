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

import sys
if r'../..' not in sys.path:
    sys.path.append(r'../..')

from server.constants import Constants
from server.exceptions import AreaError
from server.validate_assets import Validate


class ValidateAreas(Validate):
    def validate_contents(self, contents, extra_parameters=None):
        if extra_parameters is None:
            extra_parameters = dict()
        server_character_list = extra_parameters.get(
            'server_character_list', None)
        server_default_area_description = extra_parameters.get(
            'server_default_area_description', '')

        default_area_parameters = {
            'afk_delay': 0,
            'afk_sendto': 0,
            'background_tod': dict(),
            'bglock': False,
            'bullet': True,
            'cbg_allowed': False,
            'change_reachability_allowed': True,
            'default_description': server_default_area_description,
            'evidence_mod': 'FFA',
            'gm_iclock_allowed': True,
            'has_lights': True,
            'iniswap_allowed': False,
            'global_allowed': True,
            'lobby_area': False,
            'locking_allowed': False,
            'private_area': False,
            'reachable_areas': '<ALL>',
            'visible_areas': '<REACHABLE_AREAS>',
            'restricted_chars': '',
            'rollp_allowed': True,
            'rp_getarea_allowed': True,
            'rp_getareas_allowed': True,
            'scream_range': '',
            'song_switch_allowed': False,
            }

        current_area_id = 0
        area_parameters = list()
        temp_area_names = set()
        found_uncheckable_restricted_chars = False

        # Create the areas
        for item in contents:
            # Check required parameters
            if 'area' not in item:
                info = 'Area {} has no name.'.format(current_area_id)
                raise AreaError(info)
            if 'background' not in item:
                info = 'Area {} has no background.'.format(item['area'])
                raise AreaError(info)

            # Prevent reserved area names (it has a special meaning)
            reserved_names = {
                '<ALL>',
                '<REACHABLE_AREAS>',
                }

            for name in reserved_names:
                if item['area'] == name:
                    info = ('An area in your area list is called "{name}". This is a reserved '
                            'name, so it is not a valid area name. Please change its name and try '
                            'again.')
                    raise AreaError(info)

            # Prevent names that may be interpreted as a directory with . or ..
            # This prevents sending the client an entry to their music list which may be read as
            # including a relative directory
            if Constants.includes_relative_directories(item['area']):
                info = (f'Area {item["area"]} could be interpreted as referencing the current or '
                        f'parent directories, so it is invalid. Please rename the area and try '
                        f'again.')
                raise AreaError(info)

            # Check unset optional parameters
            for param in default_area_parameters:
                if param not in item:
                    item[param] = default_area_parameters[param]

            # Check use of backwards incompatible parameters
            if 'sound_proof' in item:
                info = ('The sound_proof property was defined for area {}. '
                        'Support for sound_proof was removed in favor of scream_range. '
                        'Please replace the sound_proof tag with scream_range in '
                        'your area list and try again.'.format(item['area']))
                raise AreaError(info)

            # Avoid having areas with the same name
            if item['area'] in temp_area_names:
                info = ('Two areas have the same name in area list: {}. '
                        'Please rename the duplicated areas and try again.'.format(item['area']))
                raise AreaError(info)

            # Check if any of the items were interpreted as Python Nones (maybe due to empty lines)
            for parameter in item:
                if item[parameter] is None:
                    info = ('Parameter {} is manually undefined for area {}. This can be the case '
                            'due to having an empty parameter line in your area list. '
                            'Please fix or remove the parameter from the area definition and try '
                            'again.'.format(parameter, item['area']))
                    raise AreaError(info)

            # Check and fix background tods if needed, as YAML parses this as a list of
            if item['background_tod'] != dict():
                raw_background_tod_map = item['background_tod']
                if not isinstance(raw_background_tod_map, dict):
                    info = (f'Expected background TOD for area {item["area"]} be '
                            f'one dictionary, found it was of type '
                            f'{type(raw_background_tod_map).__name__}: {raw_background_tod_map}')
                    raise AreaError(info)

                new_background_tod = dict()
                if not isinstance(raw_background_tod_map, dict):
                    info = (f'Expected background TOD for area {item["area"]} be a dictionary, '
                            f'found it was of type {type(raw_background_tod_map).__name__}: '
                            f'{raw_background_tod_map}')
                    raise AreaError(info)

                for (key, value) in raw_background_tod_map.items():
                    tod_name = str(key)
                    tod_background = str(value)
                    if not tod_name.strip():
                        info = (f'TOD name `{tod_name}` invalid for area {item["area"]}. '
                                f'Make sure the TOD name has non-space characters and try '
                                f'again.')
                        raise AreaError(info)
                    if ' ' in tod_name:
                        info = (f'TOD name `{tod_name}` invalid for area {item["area"]}. '
                                f'Make sure the TOD name has no space characters and try '
                                f'again.')
                        raise AreaError(info)
                    if '|' in tod_name:
                        info = (f'TOD name `{tod_name}` contains invalid character |.'
                                f'Make sure the TOD name does not have that character and '
                                f'try again.')
                        raise AreaError(info)
                    if '|' in tod_background:
                        info = (f'TOD background `{tod_background}` contains invalid '
                                f'character |. Make sure the TOD name does not have that '
                                f'character and try again.')
                        raise AreaError(tod_background)

                    new_background_tod[tod_name] = tod_background
                item['background_tod'] = new_background_tod

            area_parameters.append(item.copy())
            temp_area_names.add(item['area'])
            current_area_id += 1

        # Check if a reachable area is not an area name
        # Can only be done once all areas are created
        for area_item in area_parameters:
            name = area_item['area']

            reachable_areas = Constants.fix_and_setify(area_item['reachable_areas'])
            visible_areas = Constants.fix_and_setify(area_item['visible_areas'])
            scream_range = Constants.fix_and_setify(area_item['scream_range'])
            restricted_chars = Constants.fix_and_setify(area_item['restricted_chars'])

            if reachable_areas == {'<ALL>'}:
                reachable_areas = temp_area_names.copy()

            if visible_areas == {'<REACHABLE_AREAS>'}:
                visible_areas = reachable_areas.copy()

            if scream_range == {'<ALL>'}:
                scream_range = temp_area_names.copy()
            elif scream_range == {'<REACHABLE_AREAS>'}:
                scream_range = reachable_areas.copy()

            area_item['reachable_areas'] = reachable_areas
            area_item['visible_areas'] = visible_areas
            area_item['scream_range'] = scream_range
            area_item['restricted_chars'] = restricted_chars

            # Make sure no weird areas were set as reachable or visible to players or by screams
            unrecognized_areas = reachable_areas-temp_area_names
            if unrecognized_areas:
                info = (f'Area {name} has unrecognized areas {unrecognized_areas} defined as '
                        f'areas a player can reach to. Please rename the affected areas and try '
                        f'again.')
                raise AreaError(info)

            unrecognized_areas = visible_areas-temp_area_names
            if unrecognized_areas:
                info = (f'Area {name} has unrecognized areas {unrecognized_areas} defined as '
                        f'areas a player can view. Please rename the affected areas and try '
                        f'again.')
                raise AreaError(info)

            unrecognized_areas = scream_range-temp_area_names
            if unrecognized_areas:
                info = (f'Area {name} has unrecognized areas {unrecognized_areas} defined as '
                        f'areas screams can reach to. Please rename the affected areas and try '
                        f'again.')
                raise AreaError(info)

            # Make sure only characters that exist are part of the restricted char set
            if server_character_list is not None:
                unrecognized_characters = restricted_chars-set(server_character_list)
                if unrecognized_characters:
                    info = (f'Area {name} has unrecognized characters {unrecognized_characters} '
                            f'defined as restricted characters. Please make sure the characters '
                            f'exist and try again.')
                    raise AreaError(info)
            elif restricted_chars:
                found_uncheckable_restricted_chars = True

        if found_uncheckable_restricted_chars:
            info = ('WARNING: Some areas provided default restricted characters. However, no '
                    'server character list was provided, so no checks whether restricted '
                    'characters were in the character list of the server were performed.')
            print(info)

        return area_parameters


if __name__ == '__main__':
    ValidateAreas().read_sysargv_and_validate(default='areas.yaml')