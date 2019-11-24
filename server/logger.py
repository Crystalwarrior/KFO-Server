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

import datetime
import logging
import sys
import time
import traceback

from server.constants import Constants

def setup_logger(debug):
    logging.Formatter.converter = time.gmtime
    debug_formatter = logging.Formatter('[%(asctime)s UTC]%(message)s')
    srv_formatter = logging.Formatter('[%(asctime)s UTC]%(message)s')

    debug_log = logging.getLogger('debug')
    debug_log.setLevel(logging.DEBUG)

    debug_handler = logging.FileHandler('logs/debug.log', encoding='utf-8')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(debug_formatter)
    debug_log.addHandler(debug_handler)

    if not debug:
        debug_log.disabled = True

    server_log = logging.getLogger('server')
    server_log.setLevel(logging.INFO)

    current_month = "{:02d}".format(datetime.date.today().month)
    logfile_name = 'logs/server-{}-{}.log'.format(datetime.date.today().year, current_month)
    server_handler = logging.FileHandler(logfile_name, encoding='utf-8')
    server_handler.setLevel(logging.INFO)
    server_handler.setFormatter(srv_formatter)
    server_log.addHandler(server_handler)

#    rp_log = logging.getLogger('rp')
#    rp_log.setLevel(logging.INFO)

#    rp_handler = logging.FileHandler('logs/rp.log', encoding='utf-8')
#    rp_handler.setLevel(logging.INFO)
#    rp_handler.setFormatter(rp_formatter)
#    rp_log.addHandler(rp_handler)

    error_log = logging.getLogger('error')
    error_log.setLevel(logging.ERROR)

    return (debug_log, debug_handler), (server_log, server_handler)

def log_debug(msg, client=None):
    msg = parse_client_info(client) + msg
    logging.getLogger('debug').debug(msg)

def log_error(msg, server, errortype='P'):
    # errortype "C" if server raised an error as a result of a client packet.
    # errortype "P" if server raised an error for any other reason
    error_log = logging.getLogger('error')

    moment = 'logs/{}{}.log'.format(Constants.get_time_iso(), errortype)
    moment = moment.replace(':', '')
    error_handler = logging.FileHandler(moment, encoding='utf-8')

    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('[%(asctime)s UTC]%(message)s'))
    error_log.addHandler(error_handler)

    if server:
        # Add list of clients to error log
        try:
            msg += '\n\n\n= Client dump. ='
            msg += '\n*Number of clients: {}'.format(len(server.client_manager.clients))
            msg += '\n*Current clients'
            clients = sorted(server.client_manager.clients, key=lambda c: c.id)
            for c in clients:
                msg += '\n\n{}'.format(c.get_info(as_mod=True))
        except Exception:
            etype, evalue, etraceback = sys.exc_info()
            msg += '\nError generating client dump.'
            msg += '\n{}'.format("".join(traceback.format_exception(etype, evalue, etraceback)))

        # Add list of areas to error log
        try:
            msg += '\n\n\n= Area dump ='
            msg += '\n*Current area list: {}'.format(server.area_list)
            msg += '\n*Old area list: {}'.format(server.old_area_list)
            msg += '\n*Current areas:'

            for area in server.area_manager.areas:
                msg += '\n**{}'.format(area)
                for c in area.clients:
                    msg += '\n***{}'.format(c)
        except Exception:
            etype, evalue, etraceback = sys.exc_info()
            msg += '\nError generating area dump.'
            msg += '\n{}'.format("".join(traceback.format_exception(etype, evalue, etraceback)))
    else:
        # Case server was not initialized properly, so areas and clients are not set
        msg += '\nServer was not initialized, so client and area dumps could not be generated.'

    # Write and log
    error_log.error(msg)
    error_log.removeHandler(error_handler)

    log_pserver('Successfully created error log file {}'.format(moment))

def log_server(msg, client=None):
    msg = parse_client_info(client) + msg
    logging.getLogger('server').info(msg)

def log_server2(msg, client=None):
    pass

def log_print(msg, client=None):
    msg = parse_client_info(client) + msg
    current_time = Constants.get_time_iso()
    print('{}: {}'.format(current_time, msg))

def log_print2(msg, client=None):
    pass

def log_pdebug(msg, client=None):
    log_debug(msg, client=client)
    log_print(msg, client=client)

def log_pserver(msg, client=None):
    log_server(msg, client=client)
    log_print(msg, client=client)

#def log_rp(msg, client=None):
#   msg = parse_client_info(client) + msg
#    logging.getLogger('rp').info(msg)

def parse_client_info(client):
    if client is None:
        return ''
    info = client.get_ip()
    hdid = client.get_hdid()
    if client.is_mod:
        return '[{:<15}][{}][{}][MOD]'.format(info, hdid, client.id)
    return '[{:<15}][{}][{}]'.format(info, hdid, client.id)
