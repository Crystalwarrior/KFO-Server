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

"""
Module that contains the SteptimerManager class, which itself contains the Steptimer class.

A steptimer is a timer with an apparent timer value that ticks up/down a fixed length of time once
every fixed interval (a step). This allows timers that simulate slow downs or fast forwarding (for
example, a timer that ticks down one second once every real 5 seconds).
A steptimer when initialized does not start automatically, but once it starts, it will tick up/down
as described previously.
A steptimer can be paused, so that the apparent timer will stop changing. It can also be unpaused,
so the apparent timer will start changing again by the previously described interval rules.
the interval rules). The length of the first step after unpausing is set to be the current fixed
interval length minus the elapsed time in that step.
A steptimer can also be manually refreshed to obtain (an approximation of) the current timer
modified by however much of the current step happened.
Once the apparent timer ticks down below some specified minimum or ticks up above some specified
maximum, it will end automatically and be deleted. If the timer is updated above the specified
maximum but the timer is set to tick down, the timer will not end but will be set to the maximum
(a similar behavior occurs for updating to below the specified minimum for a tick up timer).
A steptimer can also be terminated before it automatically ends.

A steptimer allows the implementation different callback functions that will be executed on the
following events:
* When the steptimer ticks up/down once the firing interval elapses.
* When the steptimer ends automatically by ticking DOWN below some specified minimum timer value.
* When the steptimer ends automatically by ticking UP some specified maximum timer value.
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

    Class Attributes
    ----------------
    _FRAME_LENGTH : float
        Length of one frame in seconds assuming 60 FPS.
    _DEF_START_TIMER_VALUE : float
        Default start value the apparent timer of all managed steptimers will take.
    _DEF_MIN_TIMER_VALUE : float
        Default minimum value the apparent timer of all managed steptimers may take.
    _DEF_MAX_TIMER_VALUE : float
        Default maximum value the apparent timer of all managed steptimers may take.

    Attributes
    ----------
    _server : TsuserverDR
        Server the steptimer manager belongs to.
    _id_to_steptimer : dict of str to self.Steptimer
        Mapping of steptiomer IDs to steptimers that this manager manages.
    _steptimer_limit : int or None
        If an int, it is the maximum number of steptimers this manager supports. If None, the
        manager may manage an arbitrary number of steptimer.

    Invariants
    ----------
    1. If `self._steptimer_limit` is an int, then `len(self._id_to_steptimer) <=
       self._steptimer_limit`.
    2. For every tuple `(steptimer_id, steptimer)` in `self._id_to_group.items()`
        a. `steptimer._manager = self`.
        b. `steptimer._steptimer_id = steptimer_id`.
    3. For every pair of distinct steptimers `steptimer1` and `steptimer2` in
       `self._id_to_steptimer.values()`:
        a. `steptimer1._steptimer_id != steptimer1._steptimer_id`.
    """

    _FRAME_LENGTH = 1/60 # Length of one frame in seconds assuming 60 FPS
    _DEF_START_TIMER_VALUE = 0
    _DEF_MIN_TIMER_VALUE = 0
    _DEF_MAX_TIMER_VALUE = 60*60*6 # 6 hours in seconds

    class Steptimer:
        """
        A mutable data type representing steptimers.
        A steptimer is a timer with an apparent timer value that ticks up/down a fixed period of
        time once every fixed interval (a step).

        (Private) Attributes
        --------------------
        _server : TsuserverDR
            Server the steptimer belongs to.
        _manager : SteptimerManager
            Manager for this steptimer.
        _steptimer_id : str
            Identifier for this steptimer.
        _timer_value : float
            Number of seconds in the apparent steptimer.
        _timestep_length : float
            Number of seconds that tick from the apparent timer every step.
        _firing_interval : float
            Number of seconds that must elapse for the apparent timer to tick. It must be a
            positive number.
        _min_timer_value : float
            Minimum value the apparent timer may take. If the timer ticks below this, it will end
            automatically.
        _max_timer_value : float
            Maximum value the apparent timer may take. If the timer ticks above this, it will end
            automatically.
        _was_started : bool
            True if the apparent timer was ever started, False otherwise.
        _was_terminated : bool
            True if the steptimer was terminated, False otherwise.
        _is_paused : bool
            True if the apparent timer is paused, False otherwise.
        _just_paused : bool
            True briefly after the apparent timer is paused, False otherwise.
        _just_unpaused : bool
            True the step the apparent timer is unpaused, False otherwise.
        _last_timestep_update : float
            Time (as per time.time()) when the apparent timer last ticked or last paused, whichever
            happened later.
        _subttimestep_elapsed : float
            Computed every time the apparent timer is paused, amount of time elapsed between
            _last_timestep_update and the timer being paused.
        _task : asyncio.Task
            Actual timer task.

        Invariants
        ----------
        1. `0 <= self._min_timer_value <= self._timer_value <= self._max_timer_value`
        2. `self._firing_interval > 0`
        3. `self._timestep_length != 0`

        """

        def __init__(self, server, manager, steptimer_id, timer_value, timestep_length,
                     firing_interval, min_timer_value, max_timer_value):
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
            timer_value : float
                Number of seconds in the apparent steptimer.
            timestep_length : float, optional
                Number of seconds that tick from the apparent timer every step. Must be a non-
                negative number at least `min_timer_value` and `max_timer_value`. Defaults to
                _FRAME_LENGTH.
            firing_interval : float
                Number of seconds that must elapse for the apparent timer to tick.
            min_timer_value : float
                Minimum value the apparent timer may take. If the timer ticks below this, it will
                end automatically. It must be a non-negative number.
            max_timer_value : float, optional
                Maximum value the apparent timer may take. If the timer ticks above this, it will
                end automatically.

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

            if timer_value < min_timer_value:
                raise SteptimerError.TimerTooLowError
            if timer_value > max_timer_value:
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
            self._timer_value = timer_value

            self._timestep_length = float(timestep_length)
            self._firing_interval = float(firing_interval)
            self._min_timer_value = float(min_timer_value)
            self._max_timer_value = float(max_timer_value)

            self._was_started = False
            self._was_terminated = False
            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False
            self._was_refreshed = False
            self._last_timestep_update = time.time()
            self._time_spent_in_timestep = 0

            # This task will be an _as_timer coroutine that is meant to emulate the apparent timer.
            # This task will frequently be canceled for the purposes of updating the timer on user
            # request, or for the purposes of pausing and unpausing, and thus terminations will be
            # supprosed. The only way asyncio.CancelledError will not be ignored is via the apparent
            # timer ticking up beyond its maximum or down beyond its minimum, or via
            # .terminate_timer()
            self._task = None

            self._next_operation_ready = asyncio.Queue(maxsize=1)
            self._next_operation_ready.put_nowait(1)

        async def start_timer(self):
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

            await self._next_operation_ready.get()

            try:
                if self._was_terminated:
                    raise SteptimerError.AlreadyTerminatedSteptimerError
                if self._was_started:
                    raise SteptimerError.AlreadyStartedSteptimerError
            except Exception as exception:
                self._next_operation_ready.put_nowait(1)
                raise exception

            self._was_started = True
            async_function = self._as_timer()
            self._task = Constants.create_fragile_task(async_function)
            self._check_structure()

        async def terminate_timer(self):
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

            await self._next_operation_ready.get()

            try:
                if self._was_terminated:
                    raise SteptimerError.AlreadyTerminatedSteptimerError
            except Exception as exception:
                self._next_operation_ready.put_nowait(1)
                raise exception

            self._was_terminated = True
            self._refresh()
            self._check_structure()

        async def pause_timer(self):
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

            await self._next_operation_ready.get()

            try:
                if self._was_terminated:
                    raise SteptimerError.AlreadyTerminatedSteptimerError
                if not self._was_started:
                    raise SteptimerError.NotStartedSteptimerError
                if self._is_paused:
                    raise SteptimerError.AlreadyPausedSteptimerError
            except Exception as exception:
                self._next_operation_ready.put_nowait(1)
                raise exception

            self._is_paused = True
            self._just_paused = True
            self._update_subtimestep_elapsed()
            self._refresh()
            self._check_structure()

        async def unpause_timer(self):
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

            await self._next_operation_ready.get()

            try:
                if not self._was_started:
                    raise SteptimerError.NotStartedSteptimerError
                if self._was_terminated:
                    raise SteptimerError.AlreadyTerminatedSteptimerError
                if not self._is_paused:
                    raise SteptimerError.NotPausedSteptimerError
            except Exception as exception:
                self._next_operation_ready.put_nowait(1)
                raise exception

            self._is_paused = False
            self._was_refreshed = True
            self._just_unpaused = True
            self._update_subtimestep_elapsed()
            self._refresh()
            self._check_structure()

        async def get_time(self):
            """
            Get current apparent timer.

            Returns
            -------
            float
                Current apparent timer.

            """

            await self._next_operation_ready.get()

            value = self._timer_value
            self._next_operation_ready.put_nowait(1)
            # Note that we are storing the result in a temporary variable. This is to prevent a
            # write-after-read race
            return value

        async def get_firing_interval(self):
            """
            Get current firing interval.

            Returns
            -------
            float
                Current firing interval.

            """

            await self._next_operation_ready.get()

            value = self._firing_interval
            self._next_operation_ready.put_nowait(1)
            # Note that we are storing the result in a temporary variable. This is to prevent a
            # write-after-read race
            return value

        async def get_timestep_length(self):
            """
            Get current timestep length.

            Returns
            -------
            float
                Current timestep length.

            """

            await self._next_operation_ready.get()

            value = self._timestep_length
            self._next_operation_ready.put_nowait(1)
            # Note that we are storing the result in a temporary variable. This is to prevent a
            # write-after-read race
            return value

        async def set_time(self, new_time):
            """
            Set the apparent timer of the steptimer to `new_time`. This will also interrupt the
            current running timestep (if there is one) without calling the steptimer's firing
            callback function and start a new one.

            Parameters
            ----------
            new_time : float
                New apparent timer of the steptimer.

            Raises
            ------
            SteptimerError.TimerTooLowError
                If new_time is less than the steptimer's minimum timer value.
            SteptimerError.TimerTooHighError
                If new_time is more than the steptimer's maximum timer value.

            Returns
            -------
            None.

            """

            await self._next_operation_ready.get()

            try:
                if new_time < self._min_timer_value:
                    raise SteptimerError.TimerTooLowError
                if new_time > self._max_timer_value:
                    raise SteptimerError.TimerTooHighError
            except Exception as exception:
                self._next_operation_ready.put_nowait(1)
                raise exception

            self._last_timestep_update = time.time()
            self._time_spent_in_timestep = 0
            self._timer_value = float(new_time)
            self._refresh()
            self._check_structure()

        async def set_firing_interval(self, new_interval):
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

            await self._next_operation_ready.get()

            try:
                if new_interval <= 0:
                    raise SteptimerError.InvalidFiringIntervalError
            except Exception as exception:
                self._next_operation_ready.put_nowait(1)
                raise exception

            self._update_subtimestep_elapsed() # Update before updating new firing interval
            self._firing_interval = float(new_interval)
            self._refresh()
            self._check_structure()

        async def set_timestep_length(self, new_length):
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

            await self._next_operation_ready.get()

            try:
                if new_length == 0:
                    raise SteptimerError.InvalidTimestepLengthError
            except Exception as exception:
                self._next_operation_ready.put_nowait(1)
                raise exception

            self._update_subtimestep_elapsed() # Update before updating new timestep length
            self._timestep_length = float(new_length)
            self._refresh()
            self._check_structure()

        def _refresh(self):
            """
            Interrupt the current timestep with a cancellation order.
            The caller of this function is assumed to control self._next_operation_ready's item.
            Code in _as_timer will refill self._next_operation_ready's queue once it is done.
            If the steptimer was not started or was already terminated, this function does nothing.

            Returns
            -------
            None.

            """

            if not self._task:
                self._next_operation_ready.put_nowait(1)
                return

            self._was_refreshed = True
            self._task.cancel()
            Constants.create_fragile_task(self._await_cancellation(self._task))

        def _reset_subtimestep_elapsed(self):
            """
            Reset the timestep's sub indicators so as to indicate the start of a new timestep.
            The caller of this method is assumed to control self._next_operation_ready's item.
            This method does not reset the status of self._next_operation_ready.

            Returns
            -------
            None.

            """

            self._last_timestep_update = time.time()
            self._time_spent_in_timestep = 0

        def _update_subtimestep_elapsed(self):
            """
            Update the timestep's sub indicators with the time spent since the last update.
            The caller of this method is assumed to control self._next_operation_ready's item.
            This method does not reset the status of self._next_operation_ready.

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
            It is agnostic to self._next_operation_ready's status.

            Returns
            -------
            None.

            """

            await asyncio.sleep(0)

        async def _await_cancellation(self, old_task):
            """
            Async function that waits until it is able to properly retrieve the cancellation
            exception from `old_task`. This function assumes the task was ordered to be canceled,
            but has not yet been canceled.

            Parameters
            ----------
            old_task : asyncio.Task
                Task whose cancellation exception will be awaited.

            Returns
            -------
            None.

            """

            try:
                await old_task
            except asyncio.CancelledError:
                pass

        async def _cb_timestep_end_fn(self):
            """
            Callback function that is executed every time the steptimer is updated due to its
            firing interval elapsing.

            Returns
            -------
            None.

            """

            log_print('Timer {} ticked to {}'.format(self._steptimer_id, self._timer_value))

        async def _cb_end_min_fn(self):
            """
            Callback function that is executed once: once the steptimer time ticks DOWN to at most
            the steptimer minimum timer value.

            Returns
            -------
            None.

            """

            log_print('Timer {} min-ended at {}'.format(self._steptimer_id, self._timer_value))

        async def _cb_end_max_fn(self):
            """
            Callback function that is executed once: once the steptimer time ticks UP to at least
            the steptimer maximum timer value.

            Returns
            -------
            None.

            """

            log_print('Timer {} max-ended at {}'.format(self._steptimer_id, self._timer_value))

        async def _as_timer(self):
            """
            Async function rerpresenting the steptimer visible timer.

            Returns
            -------
            None.

            """

            self._last_timestep_update = time.time()
            self._time_spent_in_timestep = 0
            self._is_paused = False
            self._just_paused = False
            self._was_refreshed = False
            self._next_operation_ready.put_nowait(1)

            while True:
                try:
                    # This moment represents the instant a timestep resumes from pausing/refreshing
                    # or the very beginning of one.
                    self._just_paused = False
                    self._just_unpaused = False

                    # If the timer is paused, wait _firing_interval seconds again
                    if self._is_paused:
                        await asyncio.sleep(self._firing_interval)

                    # Else, if a timestep just finished without any interruptions
                    elif not self._was_refreshed:
                        self._reset_subtimestep_elapsed()

                        await self._cb_timestep_end_fn()
                        await asyncio.sleep(self._firing_interval)

                    # Otherwise, a timestep was just continued because of a refresh
                    else:
                        adapted_interval = max(0,
                                               self._firing_interval-self._time_spent_in_timestep)
                        self._was_refreshed = False

                        self._next_operation_ready.put_nowait(1)
                        await asyncio.sleep(adapted_interval)

                except asyncio.CancelledError:
                    # Code can run here for one of the following reasons
                    # 1. The timer was terminated
                    # 2. The timer was just paused
                    # 3. The timer was just refreshed
                    if self._was_terminated:
                        self._next_operation_ready.put_nowait(1)
                        break
                    elif self._is_paused:
                        self._next_operation_ready.put_nowait(1)
                        # The asynchronous waiting due to pauses is deliberately left within the
                        # try block to simplify logic, and is executed immediately after this part.
                    elif self._was_refreshed:
                        # The asynchronous refresh code is deliberately left within the try to
                        # simplify logic, and is executed immediately after this part.
                        pass
                    else:
                        # Cancelled for some weird reason that was not considered.
                        raise AssertionError('Never should have come here.')
                else:
                    # If we made it here, we made it hrough a timestep without an order to pause,
                    # refresh or terminate in it.
                    if (not self._is_paused and not self._was_refreshed):
                        self._timer_value += self._timestep_length

                        # Check if timer has gone beyond limits, and end or bound it appropriately
                        if self._timer_value <= self._min_timer_value:
                            self._timer_value = self._min_timer_value
                            if self._timestep_length < 0:
                                self._was_terminated = True
                                await self._cb_end_min_fn()
                                break
                        elif self._timer_value >= self._max_timer_value:
                            self._timer_value = self._max_timer_value
                            if self._timestep_length > 0:
                                self._was_terminated = True
                                await self._cb_end_max_fn()
                                break

                # Note that instead of notifying coroutines waiting on self._next_operation_ready
                # in a finally block we do it in each "operation end" (namely, after all code is
                # run and the only remaining code is sleeping until the next timer tickover).
                # This is to ensure that we only notify coroutines at the end of operations
                # For example, .unpause() only runs code here after it has gone through the try
                # loop once (namely, it catches CancelledError, lets it go and then reruns the try
                # block). Notifying in a finally would notify other coroutines too early that
                # the unpause is done.

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
                   '{self._firing_interval} instead.')
            assert self._firing_interval > 0, err

            # 3.
            err = f'Expected the timestep length be non-zero, found it was zero.'
            assert self._timestep_length != 0, err

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

    def new_steptimer(self, timer_value=_DEF_START_TIMER_VALUE,
                      timestep_length=_FRAME_LENGTH, firing_interval=None,
                      min_timer_value=_DEF_MIN_TIMER_VALUE, max_timer_value=_DEF_MAX_TIMER_VALUE):
        """
        Create a new steptimer with given parameters.

        Parameters
        ----------
        timer_value : float
            Number of seconds the apparent timer the steptimer will initially have. Defaults to
            _DEF_START_TIMER_VALUE.
        timestep_length : float, optional
            Number of seconds that tick from the apparent timer every step. Must be a non-
            negative number at least `min_timer_value` and `max_timer_value`. Defaults to
            _FRAME_LENGTH.
        firing_interval : float, optional
            Number of seconds that must elapse for the apparent timer to tick. Defaults to None
            (and converted to abs(timestep_length))
        min_timer_value : float, optional
            Minimum value the apparent timer may take. If the timer ticks below this, it will end
            automatically. It must be a non-negative number. Defaults to _DEF_MIN_TIMER_VALUE.
        max_timer_value : float, optional
            Maximum value the apparent timer may take. If the timer ticks above this, it will end
            automatically. Defaults to _DEF_MAX_TIMER_VALUE.

        Returns
        -------
        self.Steptimer
            The created steptimer.

        Raises
        ------
        SteptimerError.ManagerTooManySteptimersError
            If the manager is already managing its maximum number of steptimers.
        """

        if self._steptimer_limit is not None:
            if len(self._id_to_steptimer) >= self._steptimer_limit:
                raise SteptimerError.ManagerTooManySteptimersError

        if firing_interval is None:
            firing_interval = abs(timestep_length)

        # Generate a steptimer ID and the new steptimer
        steptimer_id = self._make_new_steptimer_id()
        steptimer = self.Steptimer(self._server, self, steptimer_id, timer_value, timestep_length,
                                   firing_interval, min_timer_value, max_timer_value)
        self._id_to_steptimer[steptimer_id] = steptimer

        self._check_structure()
        return steptimer

    def delete_steptimer(self, steptimer):
        """
        Delete a steptimer managed by this manager, terminateing it first if needed.

        Parameters
        ----------
        steptimer : self.Steptimer
            The steptimer to delete.

        Returns
        -------
        str
            The ID of the steptimer that was disbanded.

        Raises
        ------
        SteptimerError.ManagerDoesNotManageSteptimerError
            If the manager does not manage the target steptimer

        """

        steptimer_id = self.get_steptimer_id(steptimer) # Assert steptimer is managed by manager
        self._id_to_steptimer.pop(steptimer_id)
        try:
            steptimer.terminate()
        except SteptimerError.AlreadyTerminatedSteptimerError:
            pass

        self._check_structure()
        return steptimer_id

    def get_managed_steptimers(self):
        """
        Return (a shallow copy of) the steptimer this manager manages.

        Returns
        -------
        set of self.Steptimer
            Steptimers this manager manages.

        """

        return set(self._id_to_steptimer.values())

    def get_steptimer(self, steptimer_tag):
        """
        If `steptimer_tag` is a steptimer managed by this manager, return it.
        If it is a string and the ID of a steptimer managed by this manager, return that.

        Parameters
        ----------
        steptimer_tag: self.Steptimer or str
            Steptimers this manager manages.

        Raises
        ------
        SteptimerError.ManagerDoesNotManageSteptimerError:
            If `steptimer_tag` is a steptimer this manager does not manage.
        SteptimerError.ManagerInvalidIDError:
            If `steptimer_tag` is a str and it is not the ID of a steptimer this manager manages.

        Returns
        -------
        Steptimer
            The steptimer that matches the given tag.

        """

        # Case Steptimer
        if isinstance(steptimer_tag, self.Steptimer):
            if steptimer_tag not in self._id_to_steptimer.values():
                raise SteptimerError.ManagerDoesNotManageSteptimerError
            return steptimer_tag

        # Case Steptimer ID
        if isinstance(steptimer_tag, str):
            try:
                return self._id_to_steptimer[steptimer_tag]
            except KeyError:
                raise SteptimerError.ManagerInvalidIDError

        # Every other case
        raise SteptimerError.ManagerInvalidIDError

    def get_steptimer_id(self, steptimer_tag):
        """
        If `steptimer_tag` is the ID of a steptimer managed by this manager, return it.
        If it is a steptimer managed by this manager, return its ID.

        Parameters
        ----------
        steptimer_tag : Steptimer or str
            Steptimer this manager manages.

        Raises
        ------
        SteptimerError.ManagerDoesNotManageSteptimerError:
            If `steptimer_tag` is a steptimer this manager does not manage.
        SteptimerError.ManagerInvalidIDError:
            If `steptimer_tag` is a str and it is not the ID of a steptimer this manager manages.

        Returns
        -------
        Steptimer
            The ID of the steptimer that matches the given tag.

        """

        # Case Steptimer
        if isinstance(steptimer_tag, self.Steptimer):
            if steptimer_tag not in self._id_to_steptimer.values():
                raise SteptimerError.ManagerDoesNotManageSteptimerError
            return steptimer_tag._steptimer_id

        # Case Steptimer ID
        if isinstance(steptimer_tag, str):
            try:
                return self._id_to_steptimer[steptimer_tag]._steptimer_id
            except KeyError:
                raise SteptimerError.ManagerInvalidIDError

        # Every other case
        raise SteptimerError.ManagerInvalidIDError

    def _make_new_steptimer_id(self):
        """
        Generate a steptimer ID that no other steptimer managed by this manager has.

        Raises
        ------
        SteptimerError.ManagerTooManySteptimersError
            If the manager is already managing its maximum number of steptimers.

        Returns
        -------
        str
            A unique steptimer ID.

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
            assert steptimer._steptimer_id == steptimer_id, err

        # 3.
        for steptimer1 in self._id_to_steptimer.values():
            for steptimer2 in self._id_to_steptimer.values():
                if steptimer1 == steptimer2:
                    continue

                # 3a.
                err = (f'For steptimer manager {self}, expected that its two managed steptimers '
                       f'{steptimer1}, {steptimer2} had unique steptimer IDS, but found '
                       f'they did not. || {self}')
                assert steptimer1._steptimer_id != steptimer2._steptimer_id, err

        # Last.
        for steptimer in self._id_to_steptimer.values():
            steptimer._check_structure()
