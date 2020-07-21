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

# WARNING!
# This class will be reworked for 4.3

import asyncio
import time

from server.exceptions import ServerError

class Tasker:
    def __init__(self, server, loop):
        """
        Parameters
        ----------
        server: tsuserver.TsuserverDR
            Server of the tasker.
        loop: asyncio.<OS_event>.ProactorEventLoop
            Loop of the server's asyncio call.
        """

        self.server = server
        self.loop = loop
        self.client_tasks = dict()
        self.active_timers = dict()

    def create_task(self, client, args):
        """
        Create a new task for given client with given arguments.

        Parameters
        ----------
        client: ClientManager.Client
            Client associated to the task.
        args: list
            Arguments of the task.
        """

        # Abort old task if it exists
        try:
            old_task = self.get_task(client, args)
            if not old_task.done() and not old_task.cancelled():
                self.cancel_task(old_task)
        except KeyError:
            pass

        # Start new task
        async_function = getattr(self, args[0])(client, args[1:])
        async_future = asyncio.ensure_future(async_function, loop=self.loop)
        self.client_tasks[client.id][args[0]] = (async_future, args[1:], dict())

    def cancel_task(self, task):
        """
        Cancel current task and send order to await cancellation.

        Parameters
        ----------
        task: asyncio.Task
            Task to cancel.
        """

        task.cancel()
        asyncio.ensure_future(self.await_cancellation(task))

    def remove_task(self, client, args):
        """
        Given client and task name, remove task from server.Tasker.client_tasks and cancel it.

        Parameters
        ----------
        client: ClientManager.Client
            Client associated to the task.
        args: list
            Arguments of the task. The first one must be the task name.
        """

        task = self.client_tasks[client.id].pop(args[0])
        self.cancel_task(task[0])

    def get_task(self, client, args):
        """
        Given client and task arguments, retrieve the associated task instance.

        Parameters
        ----------
        client: ClientManager.Client
            Client associated to the task.
        args: list
            Arguments of the task.

        Returns
        -------
        asyncio.Task:
            Task object.
        """

        return self.client_tasks[client.id][args[0]][0]

    def get_task_args(self, client, args):
        """
        Given client and task arguments, retrieve the creation arguments of the task.

        Parameters
        ----------
        client: ClientManager.Client
            Client associated to the task.
        args: list
            Arguments of the task.

        Returns
        -------
        list:
            Task creation arguments.
        """

        return self.client_tasks[client.id][args[0]][1]

    def get_task_attr(self, client, args, attr):
        """
        Given client, task arguments, and an attribute name of a task, retrieve its associated
        attribute value.

        Parameters
        ----------
        client: ClientManager.Client
            Client associated to the task.
        args: list
            Arguments of the task.
        attr: str
            Attribute name.

        Returns
        -------
        Attribute value
        """

        return self.client_tasks[client.id][args[0]][2][attr]

    def set_task_attr(self, client, args, attr, value):
        """
        Given client, task arguments, attribute name of task and a value, set the attribute to
        that value.

        Parameters
        ----------
        client: ClientManager.Client
            Client associated to the task.
        args: list
            Arguments of the task.
        attr: str
            Attribute name.
        value:
            Attribute value.
        """

        self.client_tasks[client.id][args[0]][2][attr] = value


    ###
    # CURRENTLY SUPPORTED TASKS
    ###

    async def await_cancellation(self, old_task):
        # Wait until it is able to properly retrieve the cancellation exception
        try:
            await old_task
        except asyncio.CancelledError:
            pass

    async def do_nothing(self):
        while True:
            try:
                await asyncio.sleep(1)
            except KeyboardInterrupt:
                raise


    async def as_afk_kick(self, client, args):
        afk_delay, afk_sendto = args
        try:
            delay = int(afk_delay)*60 # afk_delay is in minutes, so convert to seconds
        except (TypeError, ValueError):
            info = ('The area file contains an invalid AFK kick delay for area {}: {}'.
                    format(client.area.id, afk_delay))
            raise ServerError(info)

        if delay <= 0: # Assumes 0-minute delay means that AFK kicking is disabled
            return

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        else:
            try:
                area = client.server.area_manager.get_area_by_id(int(afk_sendto))
            except Exception:
                info = ('The area file contains an invalid AFK kick destination area for area {}: '
                        '{}'.format(client.area.id, afk_sendto))
                raise ServerError(info)
            if client.area.id == afk_sendto: # Don't try and kick back to same area
                return
            if client.char_id < 0: # Assumes spectators are exempted from AFK kicks
                return
            if client.is_staff(): # Assumes staff are exempted from AFK kicks
                return

            try:
                original_area = client.area
                original_name = client.displayname
                client.change_area(area, override_passages=True, override_effects=True,
                                   ignore_bleeding=True)
            except Exception:
                pass # Server raised an error trying to perform the AFK kick, ignore AFK kick
            else:
                client.send_ooc('You were kicked from area {} to area {} for being inactive for '
                                '{} minutes.'.format(original_area.id, afk_sendto, afk_delay))

                if client.area.is_locked or client.area.is_modlocked:
                    try: # Try and remove the IPID from the area's invite list
                        client.area.invite_list.pop(client.ipid)
                    except KeyError:
                        pass # Would only happen if they joined the locked area through mod powers

                if client.party:
                    p = client.party
                    client.party.remove_member(client)
                    client.send_ooc('You were also kicked off from your party.')
                    for c in p.get_members():
                        c.send_ooc('{} was AFK kicked from your party.'.format(original_name))

    async def as_day_cycle(self, client, args):
        time_start, area_1, area_2, hour_length, hour_start, send_first_hour = args
        hour = hour_start
        minute_at_interruption = 0
        hour_paused_at = time.time() # Does not need initialization, but PyLint complains otherwise
        self.set_task_attr(client, ['as_day_cycle'], 'just_unpaused', False) # True after /clock_unpause, False after current hour elapses
        self.set_task_attr(client, ['as_day_cycle'], 'is_paused', False) # True after /clock_pause, false after /clock_unpause

        while True:
            try:
                # If an hour just finished without any interruptions
                if (not self.get_task_attr(client, ['as_day_cycle'], 'is_paused') and
                    not self.get_task_attr(client, ['as_day_cycle'], 'just_unpaused')):
                    targets = [c for c in self.server.client_manager.clients if c == client or
                               ((c.is_staff() or send_first_hour) and area_1 <= c.area.id <= area_2)]
                    for c in targets:
                        c.send_ooc('It is now {}:00.'.format('{0:02d}'.format(hour)))
                        c.send_command('CL', client.id, hour)

                    hour_started_at = time.time()
                    minute_at_interruption = 0
                    client.last_sent_clock = hour
                    await asyncio.sleep(hour_length)
                # If the clock was just unpaused, send out notif and restart the current hour
                elif (not self.get_task_attr(client, ['as_day_cycle'], 'is_paused') and
                      self.get_task_attr(client, ['as_day_cycle'], 'just_unpaused')):
                    client.send_ooc('Your day cycle in areas {} through {} has been unpaused.'
                                    .format(area_1, area_2))
                    client.send_ooc_others('(X) The day cycle initiated by {} in areas {} through {} has been unpaused.'
                                           .format(client.name, area_1, area_2), is_zstaff_flex=True)
                    self.set_task_attr(client, ['as_day_cycle'], 'just_unpaused', False)

                    minute = minute_at_interruption + (hour_paused_at - hour_started_at)/hour_length*60
                    hour_started_at = time.time()
                    minute_at_interruption = minute
                    self.server.send_all_cmd_pred('CT', '{}'.format(self.server.config['hostname']),
                                                  'It is now {}:{}.'
                                                  .format('{0:02d}'.format(hour),
                                                          '{0:02d}'.format(int(minute))),
                                                  pred=lambda c: (c == client or
                                                  (c.is_staff() and area_1 <= c.area.id <= area_2)))

                    await asyncio.sleep((60-minute_at_interruption)/60 * hour_length)


                # Otherwise, is paused. Check again in one second.
                else:
                    await asyncio.sleep(1)

                if (not self.get_task_attr(client, ['as_day_cycle'], 'is_paused') and
                    not self.get_task_attr(client, ['as_day_cycle'], 'just_unpaused')):
                    hour = (hour + 1) % 24

            except (asyncio.CancelledError, KeyError):
                # Code can run here for one of two reasons
                # 1. The timer was canceled
                # 2. The timer was just paused
                try:
                    is_paused = self.get_task_attr(client, ['as_day_cycle'], 'is_paused')
                except KeyError: # Task may be canceled, so it'll never get this values
                    is_paused = False

                if not is_paused:
                    client.send_ooc('Your day cycle in areas {} through {} has been canceled.'
                                    .format(area_1, area_2))
                    client.send_ooc_others('(X) The day cycle initiated by {} in areas {} through {} has been canceled.'
                                           .format(client.name, area_1, area_2), is_zstaff_flex=True)
                    targets = [c for c in self.server.client_manager.clients if c == client or
                               area_1 <= c.area.id <= area_2]
                    for c in targets:
                        c.send_command('CL', client.id, -1)

                    break
                else:
                    hour_paused_at = time.time()
                    minute = minute_at_interruption + (hour_paused_at - hour_started_at)/hour_length*60
                    time_at_pause = '{}:{}'.format('{0:02d}'.format(hour),
                                                   '{0:02d}'.format(int(minute)))
                    client.send_ooc('Your day cycle in areas {} through {} has been paused at {}.'
                                    .format(area_1, area_2, time_at_pause))
                    client.send_ooc_others('(X) The day cycle initiated by {} in areas {} through {} has been paused at {}.'
                                           .format(client.name, area_1, area_2, time_at_pause),
                                           is_zstaff_flex=True)
            finally:
                send_first_hour = True

    async def as_effect(self, client, args):
        start, length, effect, new_value = args # Length in seconds, already converted

        try:
            await asyncio.sleep(length)
        except asyncio.CancelledError:
            pass # Cancellation messages via send_oocs must be sent manually
        else:
            if new_value:
                client.send_ooc('The effect `{}` kicked in.'.format(effect.name))
                client.send_ooc_others('(X) {} is now subject to the effect `{}`.'
                                       .format(client.displayname, effect.name),
                                       is_zstaff_flex=True)
                effect.function(client, True)
            else:
                client.send_ooc('The effect `{}` stopped.')
                client.send_ooc_others('(X) {} is no longer subject to the effect `{}`.'
                                       .format(client.displayname, effect.name),
                                       is_zstaff_flex=True)
                effect.function(client, False)
            self.remove_task(client, [effect.async_name])

    async def as_effect_blindness(self, client, args):
        await self.as_effect(client, args+[True])

    async def as_effect_deafness(self, client, args):
        await self.as_effect(client, args+[True])

    async def as_effect_gagged(self, client, args):
        await self.as_effect(client, args+[True])

    async def as_handicap(self, client, args):
        _, length, _, announce_if_over = args
        client.is_movement_handicapped = True

        try:
            await asyncio.sleep(length)
        except asyncio.CancelledError:
            pass # Cancellation messages via send_oocs must be sent manually
        else:
            if announce_if_over and not client.is_staff():
                client.send_ooc('Your movement handicap has expired. You may move to a new area.')
        finally:
            client.is_movement_handicapped = False

    async def as_timer(self, client, args):
        _, length, name, is_public = args # Length in seconds, already converted
        client_name = client.name # Failsafe in case disconnection before task is cancelled/expires

        try:
            await asyncio.sleep(length)
        except asyncio.CancelledError:
            self.server.send_all_cmd_pred('CT', '{}'.format(self.server.config['hostname']),
                                          'Timer "{}" initiated by {} has been canceled.'
                                          .format(name, client_name),
                                          pred=lambda c: (c == client or c.is_staff() or
                                                          (is_public and c.area == client.area)))
        else:
            self.server.send_all_cmd_pred('CT', '{}'.format(self.server.config['hostname']),
                                          'Timer "{}" initiated by {} has expired.'
                                          .format(name, client_name),
                                          pred=lambda c: (c == client or c.is_staff() or
                                                          (is_public and c.area == client.area)))
        finally:
            del self.active_timers[name]
