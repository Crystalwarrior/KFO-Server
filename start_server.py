#!/usr/bin/env python3

# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-20 Chrezm/Iuvee <thechrezm@gmail.com>
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

import asyncio
import traceback

from server import logger
from server.tsuserver import TsuserverDR

def main():
    def handle_exception(loop, context):
        breakpoint()
        exception = context.get('exception')
        server.error_queue.put_nowait(exception)
        server.error_queue.put_nowait(exception)
        # An exception is put twice, because it is pulled twice: once by the server object itself
        # (so that it leaves its main loop) and once by this main() function (so that it can
        # print traceback)

    async def abnormal_shutdown(exception, server=None):
        # Print complete traceback to console
        etype, evalue, etraceback = (type(exception), exception, exception.__traceback__)
        info = 'TSUSERVERDR HAS ENCOUNTERED A FATAL PYTHON ERROR.'
        info += "\r\n" + "".join(traceback.format_exception(etype, evalue, etraceback))
        logger.log_print(info)
        logger.log_error(info, server=server, errortype='P')

        logger.log_server('Server is shutting down due to an unhandled exception.')
        logger.log_print('Attempting a graceful shutdown.')

        if not server:
            logger.log_pserver('Server has successfully shut down.')
            input("Press Enter to continue... ")
            return

        try:
            await server.normal_shutdown()
        except Exception as exception2:
            logger.log_print('Unable to gracefully shut down. Forcing a shutdown.')
            decision = input('Press Enter to continue (or input s to see reason for ungraceful '
                             'shutdown)...')
            if decision == 's':
                etype, evalue, etraceback = (type(exception2), exception2, exception2.__traceback__)
                info = "\r\n" + "".join(traceback.format_exception(etype, evalue, etraceback))

                logger.log_print(info)
                logger.log_error(info, server=server, errortype='P')
                input('Press Enter to continue...')

    server = None
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

    try:
        server = TsuserverDR()
        loop.run_until_complete(server.start())
        raise server.error_queue.get_nowait()
    except KeyboardInterrupt:
        print('') # Lame
        logger.log_pdebug('You have initiated a server shut down.')
        loop.run_until_complete(server.normal_shutdown())
        logger.log_pserver('Server has successfully shut down.')
        input("Press Enter to continue... ")
    except Exception as exception:
        loop.run_until_complete(abnormal_shutdown(exception, server=server))

if __name__ == '__main__':
    main()
