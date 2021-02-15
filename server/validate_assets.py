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

import pathlib
import sys
import traceback

from server.constants import Constants
from server.exceptions import TsuserverException


class Validate():
    def validate_contents(self, contents, extra_parameters=None):
        """
        Validate the contents of the YAML file.

        Each child class implements this.

        Parameters
        ----------
        contents : Any
            Parsed YAML.
        extra_parameters : dict
            Any extra parameters to pass to the validator when it wants to modify the contents.
            Structure of the dict depends on the class implementing validate_contents.


        Raises
        ------
        NotImplementedError
            DESCRIPTION.

        Returns
        -------
        type(contents)
            If the file is successfully validated, it returns the parsed YAML contents, with
            possible small modifications to accomodate parsing errors.

        """

        raise NotImplementedError

    def validate(self, file_name, extra_parameters=None):
        """
        Attempt to open the YAML file, parse its contents, then validate

        Parameters
        ----------
        file_name : str
            File to open.
        extra_parameters : dict
            Any extra parameters to pass to the validator when it wants to modify the contents.
            Structure of the dict depends on the class implementing validate_contents.

        Returns
        -------
        contents : Iterable
            Contents of the YAML file.

        """

        with Constants.fopen(file_name, disallow_parent_folder=False, mode='r',
                             encoding='utf-8') as file:
            contents = Constants.yaml_load(file)

        contents = self.validate_contents(contents, extra_parameters=extra_parameters)
        return contents

    @staticmethod
    def _safe_input(val):
        try:
            return input(val).strip()
        except EOFError:
            # Ctrl+Z
            sys.exit(0)
        except KeyboardInterrupt:
            # Ctrl+C
            sys.exit(0)

    def read_sysargv_and_validate(self, default=''):
        try:
            name = type(self.__class__()).__name__
            name = name.upper().replace('VALIDATE', '')
            print(f'CHECKER FOR {name}')
            default_file_name = f'../../config/{default}'
            file_name = default_file_name

            while True:
                # Get user input
                try:
                    file_name = sys.argv[1]
                except IndexError:
                    msg = ('**Enter directory for target file to check '
                           '(leave empty for default, put * for last file used in the session): ')
                    new_file_name = self._safe_input(msg)
                    if not new_file_name:
                        file_name = default_file_name
                    elif new_file_name != '*':
                        file_name = new_file_name

                # First resolve. If it can't resolve, later step would fail anyway.
                try:
                    full_path = pathlib.Path(file_name).resolve()
                    print(f'**Checking {full_path}...')

                except OSError:
                    # Should only land here for paths that cannot be resolved wo
                    print(f'Invalid file name {file_name}.')
                else:
                    if not file_name.upper().endswith('.YAML'):
                        msg = f'Invalid file name {file_name} (file extension must be .yaml)'
                        print(msg)
                    else:
                        # Now actually validate
                        try:
                            self.validate(file_name)
                        except TsuserverException as exc:
                            msg = f'**File {full_path} is NOT VALID\r\nERROR MESSAGE: {exc}'
                            print(msg)
                        else:
                            print(f'**File {full_path} is VALID.')
                finally:
                    # Prompt the user to try again.
                    do_again = ''
                    while do_again not in ['Y', 'N']:
                        do_again = self._safe_input('Try again? (y/n) ').upper()
                    if do_again == 'N':
                        break
                    print('\r\n\r\n\r\n')
        except Exception:
            print('Unhandled exception :(. We would kindly appreciate you report this.')

            etype, evalue, etraceback = sys.exc_info()

            msg = '\r\n\r\n{}'.format("".join(
                traceback.format_exception(etype, evalue, etraceback)))
            print(msg)
        finally:
            print('\r\n\r\n')
            self._safe_input('Press Enter to exit.')
