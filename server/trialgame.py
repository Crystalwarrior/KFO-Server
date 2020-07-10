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

from server.exceptions import GameError, GameWithAreasError
from server.gamewithareas import GameWithAreas

class TrialGame(GameWithAreas):
    def __init__(self, server, manager, trial_id, player_limit=None, concurrent_limit=None,
                 require_invitations=False, require_players=True, require_leaders=True,
                 require_character=False, team_limit=None, timer_limit=None,
                 areas=None, trial=None, playergroup_manager=None):
        self._trial = trial
        super().__init__(server, manager, trial_id, player_limit=player_limit,
                         concurrent_limit=concurrent_limit,
                         require_invitations=require_invitations,
                         require_players=require_players,
                         require_leaders=require_leaders,
                         require_character=require_character,
                         team_limit=team_limit, timer_limit=timer_limit,
                         areas=areas, playergroup_manager=playergroup_manager)

    def add_player(self, user):
        if not self._trial.is_player(user):
            raise GameError.UserNotPlayerError

        super().add_player(user)

    def add_area(self, area):
        if not self._trial.has_area(area):
            raise GameWithAreasError.AreaNotInGameError

        super().add_area(area)

    def get_trial(self):
        return self._trial