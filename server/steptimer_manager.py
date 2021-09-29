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

"""
Module that contains the SteptimerManager class, which itself contains the Steptimer class.

A steptimer is a timer with an apparent timer value that ticks up/down a fixed length of time (the
timestep length) once every fixed interval (the firing interval). This allows timers that simulate
slow downs or fast forwarding (for example, a timer that ticks down one second once every real
5 seconds).

A steptimer ticks up in one step if at that step the timestep length is positive. A steptimer ticks
down in one step instead if at that step the timestep length is negative.

A steptimer when initialized does not start automatically, but once it starts, it will tick up/down
as described previously.

A steptimer can be paused, so that the apparent timer will stop changing. It can also be unpaused,
so the apparent timer will start changing again by the previously described interval rules.
the interval rules). The length of the first step after unpausing is set to be the current fixed
interval length minus the elapsed time in that step.

Once the apparent timer ticks down below some specified minimum or ticks up above some specified
maximum, it will end automatically and be deleted. If the apparent timer is updated above the
specified maximum but the timer is set to tick down, the timer will not end but will be set to the
maximum (a similar behavior occurs for updating to below the specified minimum for a tick up timer).
A steptimer can also be terminated before it automatically ends.

A steptimer allows the implementation different callback functions that will be executed on the
following events:
* When the steptimer ends automatically by ticking DOWN to or below some specified minimum timer
  value.
* When the steptimer ends automatically by ticking UP to or above some specified maximum timer
  value.
* When the steptimer ticks up/down once the firing interval elapses, but is not due to end
  automatically (see previous two points)
"""

import asyncio
import time

from server.constants import Constants
from server.exceptions import SteptimerError
from server.logger import log_print

class SteptimerManager:
    """
    A mutable data type for a manager for steptimers in a server.

    Contains the steptimer object definition, as well as a mapping of steptimer IDs to their
    associated steptimers.

    The class (with its default implementation) is coroutine-safe as the default steptimer class
    is coroutine-safe and every other public method of the manager is synchronous.

    The class is NOT thread-safe.

    Overwritable Methods
    --------------------
    get_available_steptimer_id :
        Generate a new steptimer ID. Can be modified to provide different steptimer ID formats.

    """

    # (Private) Attributes
    # --------------------
    # _server : TsuserverDR
    #     Server the steptimer manager belongs to.
    # _id_to_steptimer : dict of str to self.Steptimer
    #     Mapping of steptiomer IDs to steptimers that this manager manages.
    # _steptimer_limit : int or None
    #     If an int, it is the maximum number of steptimers this manager supports. If None, the
    #     manager may manage an arbitrary number of steptimers.

    # Invariants
    # ----------
    # 1. If `self._steptimer_limit` is an int, then `len(self._id_to_steptimer) <=`
    # `self._steptimer_limit`.
    # 2. For every tuple `(steptimer_id, steptimer)` in `self._id_to_group.items()`:
    #     a. `steptimer._manager = self`.
    #     b. `steptimer._steptimer_id = steptimer_id`.
    # 3. For every pair of distinct steptimers `steptimer1` and `steptimer2` in
    # `self._id_to_steptimer.values()`:
    #     a. `steptimer1._steptimer_id != steptimer1._steptimer_id`.

    class Steptimer:
        """
        A mutable data type representing steptimers.

        A steptimer is a timer with an apparent timer value that ticks up/down a fixed period of
        time once every fixed interval (a step).

        The class is coroutine-safe as the only points where public method execution yields to a
        coroutine is after all writes were performed and the only missing step is structural
        integrity tests, which only involve reads.

        However, the class itself is NOT thread-safe, as it only uses asyncio methods that
        themselves are not thread-safe.

        Overwritable Methods
        --------------------
        _on_timestep_end :
            Callback function to be executed every time a timestep ends normally.
        _on_min_end :
            Callback function to be executed if the steptimer's apparent timer ticks down to or
            below its minimum timer value.
        _on_max_end :
            Callback function to be executed if the steptimer's apparent timer ticks up to or
            above its maximum timer value.

        Class Attributes
        ----------------
        FRAME_LENGTH : float
            Length of one frame in seconds assuming 60 FPS.
        DEF_TIMESTEP_LENGTH : float
            Default timestep length of all steptimers of this type.
        DEF_START_TIMER_VALUE : float
            Default start value the apparent timer of all steptimers of this type.
        DEF_MIN_TIMER_VALUE : float
            Default minimum value the apparent timer of all steptimers of this type.
        DEF_MAX_TIMER_VALUE : float
            Default maximum value the apparent timer of all steptimers of this type.

        """

        # (Private) Attributes
        # --------------------
        # _server : TsuserverDR
        #     Server the steptimer belongs to.
        # _manager : SteptimerManager
        #     Manager for this steptimer.
        # _steptimer_id : str
        #     Identifier for this steptimer.
        # _timer_value : float
        #     Number of seconds in the apparent steptimer.
        # _timestep_length : float
        #     Number of seconds that tick from the apparent timer every step.
        # _firing_interval : float
        #     Number of seconds that must elapse for the apparent timer to tick. It must be a
        #     positive number.
        # _min_timer_value : float
        #     Minimum value the apparent timer may take. If the timer ticks below this, it will end
        #     automatically.
        # _max_timer_value : float
        #     Maximum value the apparent timer may take. If the timer ticks above this, it will end
        #     automatically.
        # _was_started : bool
        #     True if the apparent timer was ever started, False otherwise.
        # _was_terminated : bool
        #     True if the steptimer was terminated, False otherwise.
        # _is_paused : bool
        #     True if the apparent timer is paused, False otherwise.
        # _just_paused : bool
        #     True briefly after the apparent timer is paused, False otherwise.
        # _just_unpaused : bool
        #     True briefly after the apparent timer is unpaused, False otherwise.
        # _just_refreshed : bool
        #     True briefly after the apparent timer is refreshed, False otherwise.
        # _last_timestep_update : float
        #     Time (as per time.time()) when the apparent timer last ticked or was last refreshed,
        #     whichever happened later.
        # _time_spent_in_timestep : float
        #     Time in seconds the steptimer's current timestep has run, ignoring time paused.
        # _task : asyncio.Task or None
        #     Actual timer task. _task is None as long as the steptimer is not started.

        # Invariants
        # ----------
        # 1. `0 <= self._min_timer_value <= self._timer_value <= self._max_timer_value`
        # 2. `self._firing_interval > 0`
        # 3. `self._timestep_length != 0`
        # 4. `0 <= self.DEF_MIN_TIMER_VALUE <= self.DEF_START_TIMER_VALUE
        # <= self.DEF_MAX_TIMER_VALUE`
        # 5. `self.DEF_TIMESTEP_LENGTH != 0`

        FRAME_LENGTH = 1/60 # Length of one frame in seconds assuming 60 FPS
        DEF_TIMESTEP_LENGTH = FRAME_LENGTH
        DEF_START_TIMER_VALUE = 0
        DEF_MIN_TIMER_VALUE = 0
        DEF_MAX_TIMER_VALUE = 60*60*6 # 6 hours in seconds

        def __init__(self, server, manager, steptimer_id, start_timer_value=None,
                     timestep_length=None, firing_interval=None,
                     min_timer_value=None, max_timer_value=None):
            """
            Create a new steptimer.

            Parameters
            ----------
            server : TsuserverDR
                Server the steptimer belongs to.
            manager : SteptimerManager
                Manager for this steptimer.
            steptimer_id : str
                Identifier for this steptimer.
            start_timer_value : float, optional
                Number of seconds in the apparent steptimer when it is created. Defaults to None
                (and then set to self.DEF_START_TIMER_VALUE)
            timestep_length : float, optional
                Number of seconds that tick from the apparent timer every step. Must be a non-
                negative number at least `min_timer_value` and `max_timer_value`. Defaults to None,
                (and then set to self.DEF_TIMESTEP_LENGTH).
            firing_interval : float, optional
                Number of seconds that must elapse for the apparent timer to tick. Defaults to
                None (and then set to abs(timestep_length)).
            min_timer_value : float, optional
                Minimum value the apparent timer may take. If the apparent timer ticks below this,
                it will end automatically. It must be a non-negative number. Defaults to None
                (and then set to self.DEF_MIN_TIMER_VALUE).
            max_timer_value : float, optional
                Maximum value the apparent timer may take. If the apparent timer ticks above this,
                it will end automatically. Defaults to None (and then set to
                self.DEF_MAX_TIMER_VALUE).

            Returns
            -------
            None.

            Raises
            ------
            SteptimerError.TimerTooLowError
                If `timer_value < min_timer_value`
            SteptimerError.TimerTooHighError
                If `timer_value > max_timer_value`
            SteptimerError.InvalidMinTimerValueError
                If `min_timer_value < 0`
            SteptimerError.InvalidFiringIntervalError
                If `firing_interval <= 0`
            SteptimerError.InvalidTimestepLengthError
                If `timestep_length == 0`

            """

            if start_timer_value is None:
                start_timer_value = self.DEF_START_TIMER_VALUE
            if min_timer_value is None:
                min_timer_value = self.DEF_MIN_TIMER_VALUE
            if max_timer_value is None:
                max_timer_value = self.DEF_MAX_TIMER_VALUE
            if timestep_length is None:
                timestep_length = self.DEF_TIMESTEP_LENGTH
            if firing_interval is None:
                firing_interval = abs(timestep_length)

            if start_timer_value < min_timer_value:
                raise SteptimerError.TimerTooLowError
            if start_timer_value > max_timer_value:
                raise SteptimerError.TimerTooHighError
            if min_timer_value < 0:
                raise SteptimerError.InvalidMinTimerValueError
            if firing_interval <= 0:
                raise SteptimerError.InvalidFiringIntervalError
            if timestep_length == 0:
                raise SteptimerError.InvalidTimestepLengthError

            self._server = server
            self._manager = manager
            self._steptimer_id = steptimer_id
            self._timer_value = start_timer_value

            self._timestep_length = float(timestep_length)
            self._firing_interval = float(firing_interval)
            self._min_timer_value = float(min_timer_value)
            self._max_timer_value = float(max_timer_value)

            self._was_started = False
            self._was_terminated = False
            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False
            self._due_continue_timestep_progress = False
            self._last_timestep_update = time.time()
            self._time_spent_in_timestep = 0

            # This task will be an _as_timer coroutine that is meant to emulate the apparent timer.
            # This task will frequently be canceled for the purposes of updating the timer on user
            # request, or for the purposes of pausing or refreshed, and thus terminations will be
            # suppresed. The only way asyncio.CancelledError will not be ignored is via the
            # apparent timer ticking up beyond its maximum or down beyond its minimum, or via
            # .terminate_timer()
            self._task = None
            self._check_structure()

        def get_id(self):
            """
            Return the ID of this steptimer.

            Returns
            -------
            str
                The ID of this steptimer.

            """

            return self._steptimer_id

        def was_started(self):
            """
            Return True if the apparent timer has been started already, False otherwise.

            Once a steptimer was started, this always returns True, even if it is eventually paused
            or terminated.

            Returns
            -------
            bool
                True if it was ever started, False otherwise.
            """

            return self._was_started

        def start_timer(self):
            """
            Start the steptimer. Requires the timer was not started and is not terminated.

            Returns
            -------
            None.

            Raises
            ------
            SteptimerError.AlreadyTerminatedSteptimerError:
                If the steptimer has already been terminated.
            SteptimerError.AlreadyStartedSteptimerError:
                If the steptimer has not been terminated yet but already has started.

            """

            if self._was_terminated:
                raise SteptimerError.AlreadyTerminatedSteptimerError
            if self._was_started:
                raise SteptimerError.AlreadyStartedSteptimerError

            self._was_started = True
            self._is_paused = False
            self._just_paused = False
            self._due_continue_timestep_progress = False

            self._continue_timestep()
            self._check_structure()

        def was_terminated(self):
            """
            Return True if the apparent timer has been terminated already, False otherwise.

            A steptimer can be terminated by either manually terminating it via the .terminate_timer
            method, or by it min-ending or max-ending.

            Returns
            -------
            bool
                True if it was terminated, False otherwise.
            """

            return self._was_terminated

        def terminate_timer(self):
            """
            Terminate the steptimer. Requires the timer not be terminated already.

            Returns
            -------
            None.

            Raises
            -------
            SteptimerError.AlreadyTerminatedSteptimerError:
                If the steptimer was already terminated.

            """

            if self._was_terminated:
                raise SteptimerError.AlreadyTerminatedSteptimerError

            self._was_terminated = True
            self._refresh()
            self._check_structure()

        def is_paused(self):
            """
            Return True if the apparent timer is paused, False otherwise.

            This returns False if the timer was not started!

            Returns
            -------
            bool
                True if paused, False otherwise.

            """

            return self._is_paused

        def pause_timer(self):
            """
            Pause the steptimer. Requires the timer was started, is not terminated nor paused.

            Returns
            -------
            None.

            Raises
            ------
            SteptimerError.AlreadyTerminatedSteptimerError:
                If the steptimer has been already terminated.
            SteptimerError.NotStartedSteptimerError:
                If the steptimer has not been terminated nor started yet.
            SteptimerError.AlreadyPausedSteptimerError:
                If the steptimer has not been terminated, has been started and is currently paused.

            """

            if self._was_terminated:
                raise SteptimerError.AlreadyTerminatedSteptimerError
            if not self._was_started:
                raise SteptimerError.NotStartedSteptimerError
            if self._is_paused:
                raise SteptimerError.AlreadyPausedSteptimerError

            self._is_paused = True
            self._just_paused = True
            self._update_subtimestep_elapsed()
            self._refresh()
            self._check_structure()

        def unpause_timer(self):
            """
            Unpause the steptimer. Requires the timer was started, is not terminated and is paused.

            Returns
            -------
            None.

            Raises
            ------
            SteptimerError.AlreadyTerminatedSteptimerError:
                If the steptimer has been already terminated.
            SteptimerError.NotStartedSteptimerError:
                If the steptimer has not been terminated nor started yet.
            SteptimerError.NotPausedSteptimerError:
                If the steptimer has not been terminated, has been started and is currently not
                paused.

            """

            if not self._was_started:
                raise SteptimerError.NotStartedSteptimerError
            if self._was_terminated:
                raise SteptimerError.AlreadyTerminatedSteptimerError
            if not self._is_paused:
                raise SteptimerError.NotPausedSteptimerError

            self._is_paused = False
            self._due_continue_timestep_progress = True
            self._just_unpaused = True
            self._update_subtimestep_elapsed()
            self._continue_timestep()
            self._check_structure()

        def get_time(self):
            """
            Get current apparent timer (in seconds).

            Returns
            -------
            float
                Current apparent timer.

            """

            return self._timer_value

        def get_firing_interval(self):
            """
            Get current firing interval (in seconds).

            Returns
            -------
            float
                Current firing interval.

            """

            return self._firing_interval

        def get_timestep_length(self):
            """
            Get current timestep length (in seconds).

            Returns
            -------
            float
                Current timestep length.

            """

            return self._timestep_length

        def set_time(self, new_time):
            """
            Set the apparent timer of the steptimer to `new_time`. This will also interrupt the
            current running timestep (if there is one) without calling the steptimer's firing
            callback function and start a new one.
            If `new_time` is less than the steptimer's minimum timer value, the timer will be
            adapted to take this minimum value instead. Similarly, if `new_time` is more than the
            steptimer's maximum timer value, the timer will be adapted to take this maximum value
            instead.

            Parameters
            ----------
            new_time : float
                New apparent timer of the steptimer.

            Returns
            -------
            None.

            """

            self._timer_value = float(new_time)
            if self._timer_value < self._min_timer_value:
                self._timer_value = self._min_timer_value
            elif self._timer_value > self._max_timer_value:
                self._timer_value = self._max_timer_value

            self._refresh()
            self._continue_timestep()
            self._check_structure()

        def set_firing_interval(self, new_interval):
            """
            Update the firing interval of the steptimer for all future timesteps. If a timestep
            has started when this function is scheduled to run, the current timestep will be
            readapted to finish in this new firing interval as follows:
            * Assume length x of the 'current' timestep with orig has elapsed.
            * Then, the current timestep will be adapted to have length max(0, new_interval-x)

            Parameters
            ----------
            new_interval : float
                New firing interval. It must be a positive number.

            Raises
            ------
            SteptimerError.InvalidFiringIntervalError
                If `new_interval <= 0`.

            Returns
            -------
            None.

            """

            if new_interval <= 0:
                raise SteptimerError.InvalidFiringIntervalError

            self._update_subtimestep_elapsed() # Update before updating new firing interval
            self._firing_interval = float(new_interval)
            self._refresh()
            self._continue_timestep()
            self._check_structure()

        def set_timestep_length(self, new_length):
            """
            Update the timestep length of the steptimer for all future timesteps and the current
            one if one has started by the time this function is scheduled to run.

            Parameters
            ----------
            new_length : float
                New timestep length. It must not be zero.

            Raises
            ------
            SteptimerError.InvalidTimestepLengthError
                If `new_length == 0`.

            Returns
            -------
            None.

            """

            if new_length == 0:
                raise SteptimerError.InvalidTimestepLengthError

            self._update_subtimestep_elapsed() # Update before updating new timestep length
            self._timestep_length = float(new_length)
            self._refresh()
            self._continue_timestep()
            self._check_structure()

        def change_time_by(self, time_difference):
            """
            Change the apparent timer of the steptimer by `time_difference`. This will also
            nterrupt the current running timestep (if there is one) without calling the
            steptimer's firing callback function and start a new one.
            If the new apparent timer time is less than the steptimer's minimum timer value, the
            timer will be adapted to take this minimum value instead. Similarly, if the new
            apparent timer time is more than steptimer's maximum timer value, the timer will be
            adapted to take this maximum value instead.

            Parameters
            ----------
            time_difference : float
                Amount of time to change the apparent timer by (possibly zero or negative).

            Returns
            -------
            None.

            """

            self._last_timestep_update = time.time()
            self._time_spent_in_timestep = 0

            self._timer_value += float(time_difference)
            if self._timer_value < self._min_timer_value:
                self._timer_value = self._min_timer_value
            elif self._timer_value > self._max_timer_value:
                self._timer_value = self._max_timer_value

            self._refresh()
            self._continue_timestep()
            self._check_structure()

        def _continue_timestep(self):
            if self._was_terminated:
                # This code should only run if it takes longer for the timer to be terminated than
                # the firing interval.
                return

            if self._timer_value <= self._min_timer_value:
                self._timer_value = self._min_timer_value
                if self._timestep_length < 0:
                    self._was_terminated = True
                    self._on_min_end()
                    return
            elif self._timer_value >= self._max_timer_value:
                self._timer_value = self._max_timer_value
                if self._timestep_length > 0:
                    self._was_terminated = True
                    self._on_max_end()
                    return

            # This moment represents the instant a timestep resumes from pausing/refreshing
            # or the very beginning of one.
            self._just_paused = False
            self._just_unpaused = False

            # If the timer is paused, wait _firing_interval seconds again
            if self._is_paused:
                return

            # Else, if a timestep just finished without any interruptions
            # Reset time spent in timestep and last update to timestep
            if not self._due_continue_timestep_progress:
                self._reset_subtimestep_elapsed()
                self._on_timestep_end()

            adapted_interval = self._firing_interval-self._time_spent_in_timestep
            if adapted_interval < 0:
                adapted_interval = 0

            self._due_continue_timestep_progress = False
            self._task = Constants.create_fragile_task(self._wait_timestep_end(adapted_interval))

        async def _wait_timestep_end(self, time_to_end):
            start_time = time.perf_counter()
            async def _wait():
                while time.perf_counter() < start_time+time_to_end:
                    await asyncio.sleep(0)
            await _wait()
            # await asyncio.sleep(time_to_end)
            # b = time.perf_counter()
            # print(b-a)
            self._timer_value += self._timestep_length
            self._continue_timestep()

        def _refresh(self):
            """
            Interrupt the current timestep with a cancellation order.
            If the steptimer is not currently running, this function does nothing.

            Returns
            -------
            None.

            """

            if not self._task:
                return

            self._due_continue_timestep_progress = True
            Constants.create_fragile_task(self._cancel_and_await(self._task))

        def _reset_subtimestep_elapsed(self):
            """
            Reset the timestep's sub indicators so as to indicate the start of a new timestep.

            Returns
            -------
            None.

            """

            self._last_timestep_update = time.time()
            self._time_spent_in_timestep = 0

        def _update_subtimestep_elapsed(self):
            """
            Update the timestep's sub indicators with the time spent since the last update.

            Returns
            -------
            None.

            """

            time_now = time.time()
            # If the timer is paused but was not just paused, this is just
            # self._time_spent_in_timestep
            if (self._is_paused and not self._just_paused) or self._just_unpaused:
                newest_last_timestep_update = self._last_timestep_update
            else:
                newest_last_timestep_update = time_now
            # Otherwise, this is constantly changing
            # so find real time elapsed since last update to subtimestep_elapsed
            self._time_spent_in_timestep += newest_last_timestep_update - self._last_timestep_update
            self._last_timestep_update = time_now

        async def _no_action(self):
            """
            Dummy function that does nothing, but allows other coroutines to start running.

            Returns
            -------
            None.

            """

            await asyncio.sleep(0)

        async def _cancel_and_await(self, old_task):
            """
            Async function that cancels `old_task` and awaits until it is able to properly retrieve
            the cancellation exception from `old_task`. This function assumes the task has not been
            cancelled yet.

            Parameters
            ----------
            old_task : asyncio.Task
                Task to cancel

            Returns
            -------
            None.

            """

            try:
                old_task.cancel()
                await old_task
            except asyncio.CancelledError:
                pass

        def _on_timestep_end(self):
            """
            Callback function that is executed every time the steptimer is updated due to its
            firing interval elapsing.

            Returns
            -------
            None.

            """

            # log_print('Timer {} ticked to {}'.format(self._steptimer_id, self._timer_value))

        def _on_min_end(self):
            """
            Callback function that is executed once: once the steptimer time ticks DOWN to at most
            the steptimer minimum timer value.

            Returns
            -------
            None.

            """

            # log_print('Timer {} min-ended at {}'.format(self._steptimer_id, self._timer_value))

        def _on_max_end(self):
            """
            Callback function that is executed once: once the steptimer time ticks UP to at least
            the steptimer maximum timer value.

            Returns
            -------
            None.

            """

            # log_print('Timer {} max-ended at {}'.format(self._steptimer_id, self._timer_value))

        def _check_structure(self):
            """
            Assert that all invariants in the class description are satisfied.

            Returns
            -------
            None.

            Raises
            ------
            AssertionError:
                If any of the invariants are not satisfied.
            """

            # 1.
            err = (f'Expected the steptimer minimum timer value be a non-negative number, found '
                   f'it was {self._min_timer_value} instead.')
            assert self._min_timer_value >= 0, err

            err = (f'Expected the steptimer timer value be at least the minimum timer value '
                   f'{self._min_timer_value}, found it was {self._timer_value} instead.')
            assert self._timer_value >= self._min_timer_value, err

            err = (f'Expected the steptimer timer value be at most the maximum timer value '
                   f'{self._max_timer_value}, found it was {self._timer_value} instead.')
            assert self._timer_value <= self._max_timer_value, err

            # 2.
            err = (f'Expected the firing interval be a positive number, found it was '
                   f'{self._firing_interval} instead.')
            assert self._firing_interval > 0, err

            # 3.
            err = 'Expected the timestep length be non-zero, found it was zero.'
            assert self._timestep_length != 0, err

            # 4.
            err = (f'Expected the default steptimer minimum timer value be a non-negative number, '
                   f'found it was {self.DEF_MIN_TIMER_VALUE} instead.')
            assert self.DEF_MIN_TIMER_VALUE >= 0, err

            err = (f'Expected the default steptimer timer value be at least the default minimum '
                   f'timer value {self.DEF_MIN_TIMER_VALUE}, found it was '
                   f'{self.DEF_START_TIMER_VALUE}.')
            assert self.DEF_START_TIMER_VALUE >= self.DEF_MIN_TIMER_VALUE, err

            err = (f'Expected the default steptimer timer value be at most the default maximum '
                   f'timer value {self.DEF_MAX_TIMER_VALUE}, found it was '
                   f'{self.DEF_START_TIMER_VALUE} instead.')
            assert self.DEF_START_TIMER_VALUE <= self.DEF_MAX_TIMER_VALUE, err

            # 5.
            err = 'Expected the default timestep length be non-zero, found it was zero.'
            assert self.DEF_TIMESTEP_LENGTH != 0, err

    def __init__(self, server, steptimer_limit=None):
        """
        Create a steptimer manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this steptimer manager belongs to.
        steptimer_limit : int, optional
            The maximum number of steptimers this manager can handle. The default is None.

        """

        self._server = server
        self._steptimer_limit = steptimer_limit

        self._id_to_steptimer = dict()

    def new_steptimer(self, steptimer_type=None, start_timer_value=None, timestep_length=None,
                      firing_interval=None, min_timer_value=None, max_timer_value=None):
        """
        Create a new steptimer with given parameters managed by this manager.

        Parameters
        ----------
        steptimer_type : SteptimerManager.Steptimer, optional
            Class of steptimer that will be produced. Defaults to None (and converted to
            self.Steptimer)
        start_timer_value : float, optional
            Number of seconds the apparent timer the steptimer will initially have. Defaults to
            None (will use the default from `steptimer_type`).
        timestep_length : float, optional
            Number of seconds that tick from the apparent timer every step. Must be a non-
            negative number at least `min_timer_value` and `max_timer_value`. Defaults to
            None (will use the default from `steptimer_type`).
        firing_interval : float, optional
            Number of seconds that must elapse for the apparent timer to tick. Defaults to None
            (and converted to abs(timestep_length))
        min_timer_value : float, optional
            Minimum value the apparent timer may take. If the timer ticks below this, it will end
            automatically. It must be a non-negative number. Defaults to None (will use the
            default from `steptimer_type`.)
        max_timer_value : float, optional
            Maximum value the apparent timer may take. If the timer ticks above this, it will end
            automatically. Defaults to None (will use the default from `steptimer_type`).

        Returns
        -------
        self.Steptimer
            The created steptimer.

        Raises
        ------
        SteptimerError.ManagerTooManySteptimersError
            If the manager is already managing its maximum number of steptimers.

        """

        # Check if adding a new steptimer to manage would be one too many
        if self._steptimer_limit is not None:
            if len(self._id_to_steptimer) >= self._steptimer_limit:
                raise SteptimerError.ManagerTooManySteptimersError

        # Fill in default values
        if steptimer_type is None:
            steptimer_type = self.Steptimer
        if firing_interval is None and timestep_length is not None:
            firing_interval = abs(timestep_length)

        # Generate a steptimer ID and the new steptimer
        steptimer_id = self.get_available_steptimer_id()
        steptimer = steptimer_type(self._server, self, steptimer_id,
                                   start_timer_value=start_timer_value,
                                   timestep_length=timestep_length,
                                   firing_interval=firing_interval,
                                   min_timer_value=min_timer_value,
                                   max_timer_value=max_timer_value)
        self._id_to_steptimer[steptimer_id] = steptimer

        self._check_structure()
        return steptimer

    def delete_steptimer(self, steptimer):
        """
        Delete a steptimer managed by this manager, terminating it first if needed.

        Parameters
        ----------
        steptimer : SteptimerManager.Steptimer
            The steptimer to delete.

        Returns
        -------
        str
            The ID of the steptimer that was deleted.

        Raises
        ------
        SteptimerError.ManagerDoesNotManageSteptimerError
            If the manager does not manage the target steptimer.

        """

        # Assert steptimer is managed by manager.
        if not self.manages_steptimer(steptimer):
            raise SteptimerError.ManagerDoesNotManageSteptimerError

        steptimer_id = steptimer.get_id()
        # Pop the steptimer. By doing this now, it helps guard the class' only call to an
        # asynchronous function. In particular, once .delete_steptimer() is called on a managed
        # steptimer, these two lines will always execute, which will prevent the steptimer to
        # terminate from influencing other public method calls of the manager.
        self._id_to_steptimer.pop(steptimer_id)

        try:
            steptimer.terminate_timer()
        except SteptimerError.AlreadyTerminatedSteptimerError:
            pass

        # As the steptimer is popped, it will no longer be referred to in the internal structure
        # check function.
        self._check_structure()
        return steptimer_id

    def manages_steptimer(self, steptimer):
        """
        Return True if the steptimer is managed by this manager, False otherwise.

        Parameters
        ----------
        steptimer : SteptimerManager.StepTimer
            The steptimer to check.

        Returns
        -------
        bool
            True if the manager manages this steptimer, False otherwise.

        """

        return steptimer in self._id_to_steptimer.values()

    def get_steptimers(self):
        """
        Return (a shallow copy of) the steptimers this manager manages.

        Returns
        -------
        set of SteptimerManager.Steptimer
            Steptimers this manager manages.

        """

        return set(self._id_to_steptimer.values())

    def get_steptimer_by_id(self, steptimer_id):
        """
        If `steptimer_tag` is the ID of a steptimer managed by this manager, return that steptimer.

        Parameters
        ----------
        steptimer_id: str
            ID of steptimer this manager manages.

        Returns
        -------
        SteptimerManager.Steptimer
            The steptimer whose ID matches the given ID.

        Raises
        ------
        SteptimerError.ManagerInvalidSteptimerIDError:
            If `steptimer_id` is not the ID of a steptimer this manager manages.

        """

        try:
            return self._id_to_steptimer[steptimer_id]
        except KeyError:
            raise SteptimerError.ManagerInvalidSteptimerIDError

    def get_steptimer_ids(self):
        """
        Return (a shallow copy of) the IDs of all steptimers managed by this manager.

        Returns
        -------
        set of str
            The IDs of all managed steptimers.

        """

        return set(self._id_to_steptimer.keys())

    def get_available_steptimer_id(self):
        """
        Get a steptimer ID that no other steptimer managed by this manager has.

        Returns
        -------
        str
            A unique steptimer ID.

        Raises
        ------
        SteptimerError.ManagerTooManySteptimersError
            If the manager is already managing its maximum number of steptimers.

        """

        steptimer_number = 0
        while self._steptimer_limit is None or steptimer_number < self._steptimer_limit:
            new_steptimer_id = "st{}".format(steptimer_number)
            if new_steptimer_id not in self._id_to_steptimer.keys():
                return new_steptimer_id
            steptimer_number += 1
        raise SteptimerError.ManagerTooManySteptimersError

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        if self._steptimer_limit is not None:
            err = (f'For steptimer manager {self}, expected that it managed at most '
                   f'{self._steptimer_limit} steptimers, but found it managed '
                   f'{len(self._id_to_steptimer)} steptimers. || {self}')
            assert len(self._id_to_steptimer) <= self._steptimer_limit, err

        # 2.
        for (steptimer_id, steptimer) in self._id_to_steptimer.items():
            # 2a.
            err = (f'For steptimer manager {self}, expected that its managed steptimer '
                   f'{steptimer} recognized that it was managed by it, but found it did not. '
                   f'|| {self}')
            assert steptimer._manager == self, err

            # 2b.
            err = (f'For steptimer manager {self}, expected that steptimer {steptimer} '
                   f'that appears in the ID to steptimer mapping has the same ID as in the '
                   f'mapping, but found it did not. || {self}')
            assert steptimer.get_id() == steptimer_id, err

        # 3.
        for steptimer1 in self._id_to_steptimer.values():
            for steptimer2 in self._id_to_steptimer.values():
                if steptimer1 == steptimer2:
                    continue

                # 3a.
                err = (f'For steptimer manager {self}, expected that its two managed steptimers '
                       f'{steptimer1}, {steptimer2} had unique steptimer IDS, but found '
                       f'they did not. || {self}')
                assert steptimer1.get_id() != steptimer2.get_id(), err

        # Last.
        for steptimer in self._id_to_steptimer.values():
            steptimer._check_structure()
