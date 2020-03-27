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

from server.playergroup_manager import PlayerGroupManager

"""
Module that contains the GameManager class, which itself contains the Game subclass.

Games are player groups that maintain first-in-first-out queues of arbitrary many TsuserverDR
packets to send to its players.

Each game is managed by a game manager, which iself are player group managers.
"""

class GameManager(PlayerGroupManager):
    class PlayerGroup:
        """
        Not to be used.
        """

    class Game(PlayerGroupManager.PlayerGroup):
        def enqueue_packet(self, packet):
            pass

        def dequeue_packet(self):
            pass

        def create_timer(self, timer_length, callback_function, callback_arguments):
            pass

        def cancel_timer(self, timer_id):
            pass

        def get_timer(self, timer_id):
            pass

        def _check_structure(self):
            super()._check_structure()

    def make_new_group_id(self):
        pass

    def _check_structure(self):
        super()._check_structure()
