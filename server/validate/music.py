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
from server.exceptions import ServerError
from server.validate_assets import Validate


class ValidateMusic(Validate):
    def validate_contents(self, contents, extra_parameters=None):
        # Check music list contents is indeed a list
        if not isinstance(contents, list):
            msg = (f'Expected the music list to be a list, got a '
                   f'{type(contents).__name__}: {contents}.')
            raise ServerError.FileSyntaxError(msg)

        # Check top level description is ok
        for (i, item) in enumerate(contents.copy()):
            if item is None:
                msg = (f'Expected all music list items to be defined, but item {i} was not.')
                raise ServerError.FileSyntaxError(msg)
            if not isinstance(item, dict):
                msg = (f'Expected all music list items to be dictionaries, but item '
                       f'{i}: {item} was not a dictionary.')
                raise ServerError.FileSyntaxError(msg)
            if set(item.keys()) != {'category', 'songs'}:
                msg = (f'Expected all music list items to have exactly two keys: category and '
                       f'songs, but item {i} had keys {set(item.keys())}')
                raise ServerError.FileSyntaxError(msg)

            category, songs = item['category'], item['songs']
            if category is None:
                msg = (f'Expected all music list categories to be defined, but category {i} was '
                       f'not.')
                raise ServerError.FileSyntaxError(msg)
            if songs is None:
                msg = (f'Expected all music list song descriptions to be defined, but song '
                       f'description {i} was not.')
                raise ServerError.FileSyntaxError(msg)

            if not isinstance(category, (str, float, int, bool, complex)):
                msg = (f'Expected all music list category names to be strings or numbers, but '
                       f'category {i}: {category} was not a string or number.')
                raise ServerError.FileSyntaxError(msg)
            if not isinstance(songs, list):
                msg = (f'Expected all music list song descriptions to be a list, but '
                       f'description {i}: {songs} was not a list.')
                raise ServerError.FileSyntaxError(msg)

        # Check each song description dictionary is ok
        for (i, item) in enumerate(contents.copy()):
            category = item['category']
            songs = item['songs']
            for (j, song) in enumerate(songs):
                if song is None:
                    msg = (f'Expected all music list song descriptions to be defined, but song '
                           f'description {j} in category {i}: {category} was not defined.')
                    raise ServerError.FileSyntaxError(msg)
                if not isinstance(song, dict):
                    msg = (f'Expected all music list song descriptions to be dictionaries: but '
                           f'song description {j} in category {i}: {category} was not a '
                           f'dictionary: {song}.')
                    raise ServerError.FileSyntaxError(msg)
                if set(song.keys()) not in [{'name'}, {'name', 'length'}]:
                    msg = (f'Expected all music list songs to have exactly the keys: name, or name '
                           f'and length, but song description {j} in category {i}: {category} had '
                           f'keys {set(song.keys())}.')
                    raise ServerError.FileSyntaxError(msg)

                if 'length' not in song:
                    name, length = song['name'], -1
                else:
                    name, length = song['name'], song['length']

                if not isinstance(name, (str, float, int, bool, complex)):
                    msg = (f'Expected all music list song names to be strings or numbers, but '
                           f'song {j}: {name} in category {i}: {category} was not a string or '
                           f'number.')
                    raise ServerError.FileSyntaxError(msg)
                if not isinstance(length, (int, float)):
                    msg = (f'Expected all music list song lengths to be numbers, but song {j}: '
                           f'{name} in category {i}: {category} had non-numerical length {length}.')
                    raise ServerError.FileSyntaxError(msg)

                # Prevent names that may be interpreted as a directory with . or ..
                # This prevents sending the client an entry to their music list which may be read as
                # including a relative directory
                if Constants.includes_relative_directories(name):
                    info = (f'Music {name} could be interpreted as referencing current or '
                            f'parent directories, so it is invalid.')
                    raise ServerError.FileSyntaxError(info)
        return contents


if __name__ == '__main__':
    ValidateMusic().read_sysargv_and_validate(default='music.yaml')
