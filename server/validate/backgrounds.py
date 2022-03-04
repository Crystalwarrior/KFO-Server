# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-22 Chrezm/Iuvee <thechrezm@gmail.com>
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

from typing import List

import sys
if r'../..' not in sys.path:
    sys.path.append(r'../..')

from server.exceptions import ServerError
from server.validate_assets import Validate


class ValidateBackgrounds(Validate):
    def validate_contents(self, contents, extra_parameters=None) -> List[str]:
        # Check background contents is indeed a list of strings
        if not isinstance(contents, list):
            msg = (f'Expected the background list to be a list, got a '
                   f'{type(contents).__name__}: {contents}.')
            raise ServerError.FileSyntaxError(msg)

        for (i, background) in enumerate(contents.copy()):
            if background is None:
                msg = (f'Expected all background names to be defined, '
                       f'found background {i} was not.')
                raise ServerError.FileSyntaxError(msg)
            if not isinstance(background, (str, float, int, bool, complex)):
                msg = (f'Expected all background names to be strings or numbers, '
                       f'found background {i}: {background} was not a string or number.')
                raise ServerError.FileSyntaxError(msg)

            # Otherwise, background i is valid. Cast it as string to deal with YAML doing
            # potential casting of its own
            contents[i] = str(background)

        return contents


if __name__ == '__main__':
    ValidateBackgrounds().read_sysargv_and_validate(default='backgrounds.yaml')
