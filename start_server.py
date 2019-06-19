#!/usr/bin/env python3

# tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import traceback
import server.logger

from time import asctime, localtime, time
from server.tsuserver import TsuServer3

def main():
    my_server = TsuServer3()
    my_server.start()

if __name__ == '__main__':
    try:
        server.logger.log_print('Starting...')
        main()
    except KeyboardInterrupt:
        raise
    except Exception:
        # Print complete traceback to console
        etype, evalue, etraceback = sys.exc_info()
        tb = traceback.extract_tb(tb=etraceback)
        current_time = asctime(localtime(time()))
        file, line_num, module, func = tb[-1]
        file = file[file.rfind('\\')+1:] # Remove unnecessary directories

        server.logger.log_print('TSUSERVER HAS ENCOUNTERED A PYTHON ERROR.')
        traceback.print_exception(etype, evalue, etraceback)
        server.logger.log_print('Server is shutting down.')