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
Module that contains the StepTimerManager class, which itself contains the StepTimer class.

A step timer is a timer with an apparent timer value that ticks up/down a fixed period of time once
every fixed interval (a step). This allows timers that simulate slow downs or fast forwarding (for
example, a timer that ticks down one second once every real 5 seconds).
A step timer when initialized does not start automatically, but once it starts, it can be paused
(where the apparent timer will not change) and unpaused (where the apparent timer will change by
the interval rules). The length of the first step after unpausing is set to be the current fixed
interval length minus the elapsed time in that step.
Once the apparent timer ticks down below some specified minimum or ticks up above some specified
maximum, it will end automatically and be deleted. If the timer is updated above the specified
maximum but the timer is set to tick down, the timer will not end but will be set to the maximum
(a similar behavior occurs for updating to below the specified minimum for a tick up timer).
A step timer can also be canceled before it automatically ends.

A step timer allows the implementation different callback functions that will be executed on the
following events:
* When the step timer starts.
* When the step timer ticks up/down once the interval elapses.
* When the step timer is paused.
* When the step timer is unpaused.
* When the step timer ends automatically by ticking DOWN below 0.
* When the step timer ends automatically by ticking UP above _MAXIMUM_TIMER_VALUE
* When the step timer is canceled.
"""

import asyncio
import time

from server.exceptions import StepTimerError
from server.logger import log_print

class StepTimerManager:
    class StepTimer:
        """
        A mutable data type representing step timers.
        A step timer is a timer with an apparent timer value that ticks up/down a fixed period of
        time once every fixed interval (a step).

        Class Attributes
        ----------------
        _FRAME_LENGTH : float
            Length of one frame in seconds assuming 60 FPS.
        _DEF_MIN_TIMER_VALUE : float
            Default minimum value the apparent timer may take.
        _DEF_MAX_TIMER_VALUE : float
            Default maximum value the apparent timer may take.

        Attributes
        ----------
        _server : TsuserverDR
            Server the step timer group belongs to.
        _manager : StepTimerManager
            Manager for this step timer.
        _loop: asyncio.<OS_event>.ProactorEventLoop
            Loop of the server's asyncio call.
        _steptimer_id : str
            Identifier for this step timer.
        _timer_value : float
            Number of seconds in the apparent step timer.
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
        _cb_start_args : tuple
            Arguments to the function called on step timer start.
        _cb_firing_args : tuple
            Arguments to the function called on step timer ticking.
        _cb_pause_args : tuple
            Arguments to the function called on step timer pause.
        _cb_unpause_args : tuple
            Arguments to the function called on step timer unpause.
        _cb_end_min_args : tuple
            Arguments to the function called on step timer ticking down below _min_timer_value.
        _cb_end_max_args : tuple
            Arguments to the function called on step timer ticking up above _max_timer_value.
        _cb_cancel_args : tuple
            Arguments to the function called on step timer canceled externally.
        _was_started : bool
            True if the apparent timer was ever started, False otherwise.
        _was_canceled : bool
            True if the step timer was canceled, False otherwise.
        _is_paused : bool
            True if the apparent timer is paused, False otherwise.
        _just_paused : bool
            True the step the apparent timer is paused, False otherwise.
        _just_unpaused : bool
            True the step the apparent timer is unpaused, False otherwise.
        _last_timestep_time : float
            Time (as per time.time()) when the apparent timer last ticked or last paused, whichever
            happened later.
        _subttimestep_elapsed : float
            Computed every time the apparent timer is paused, amount of time elapsed between
            _last_timestep_time and the timer being paused.
        _task : asyncio.Task
            Actual timer task.

        Invariants
        ----------
        1. `0 <= self._min_timer_value <= self._timer_value <= self._max_timer_value`
        2. `0 < self._firing_interval`
        """

        _FRAME_LENGTH = 1/60 # Length of one frame in seconds assuming 60 FPS
        _DEF_MIN_TIMER_VALUE = 0
        _DEF_MAX_TIMER_VALUE = 60*60*6 # 6 hours in seconds

        def __init__(self, server, manager, loop, steptimer_id, timer_value,
                     timestep_length=_FRAME_LENGTH, firing_interval=None,
                     min_timer_value=_DEF_MIN_TIMER_VALUE, max_timer_value=_DEF_MAX_TIMER_VALUE,
                     cb_start_args=tuple(), cb_firing_args=tuple(),
                     cb_pause_args=tuple(), cb_unpause_args=tuple(),
                     cb_end_min_args=tuple(), cb_end_max_args=tuple(),
                     cb_cancel_args=tuple()):
            """
            Create a new step timer.

            Parameters
            ----------
            server : TsuserverDR
                Server the step timer group belongs to.
            manager : StepTimerManager
                Manager for this step timer.
            loop: asyncio.<OS_event>.ProactorEventLoop
                Loop of the server's asyncio call.
            steptimer_id : str
                Identifier for this step timer.
            timer_value : float
                Number of seconds in the apparent step timer.
            timestep_length : float, optional
                Number of seconds that tick from the apparent timer every step. Must be a non-
                negative number at least `min_timer_value` and `max_timer_value`. Defaults to
                _FRAME_LENGTH.
            firing_interval : float, optional
                Number of seconds that must elapse for the apparent timer to tick. Defaults to
                None (and converted to abs(timestep_length))
            min_timer_value : float, optional
                Minimum value the apparent timer may take. If the timer ticks below this, it will
                end automatically. It must be a non-negative number. Defaults to
                _DEF_MIN_TIMER_VALUE.
            max_timer_value : float, optional
                Maximum value the apparent timer may take. If the timer ticks above this, it will
                end automatically. Defaults to _DEF_MAX_TIMER_VALUE.
            cb_start_args : tuple
                Arguments to the function called on step timer start. Defaults to an empty tuple.
            cb_firing_args : tuple
                Arguments to the function called on step timer ticking. Defaults to an empty tuple.
            cb_pause_args : tuple
                Arguments to the function called on step timer pause. Defaults to an empty tuple.
            cb_unpause_args : tuple
                Arguments to the function called on step timer unpause. Defaults to an empty tuple.
            cb_end_min_args : tuple
                Arguments to the function called on step timer ticking down below _min_timer_value.
                Defaults to an empty tuple.
            cb_end_max_args : tuple
                Arguments to the function called on step timer ticking up above _max_timer_value.
                Defaults to an empty tuple.
            cb_cancel_args : tuple
                Arguments to the function called on step timer canceled externally. Defaults to an
                empty tuple.

            Returns
            -------
            None.

            Raises
            ------
            StepTimerError.InvalidStepTimerValueError
                If `timer_value > max_timer_value` or `timer_value < min_timer_value`.
            StepTimerError.InvalidMinTimerValueError
                If `min_timer_value < 0`

            """

            if timer_value > max_timer_value or timer_value < min_timer_value:
                raise StepTimerError.InvalidStepTimerValueError
            if min_timer_value < 0:
                raise StepTimerError.InvalidMinTimerValueError

            if firing_interval is None:
                firing_interval = abs(timestep_length)

            self._server = server
            self._manager = manager
            self._loop = loop
            self._steptimer_id = steptimer_id
            self._timer_value = timer_value

            self._timestep_length = timestep_length
            self._firing_interval = firing_interval
            self._min_timer_value = min_timer_value
            self._max_timer_value = max_timer_value
            self._cb_start_args = cb_start_args
            self._cb_firing_args = cb_firing_args
            self._cb_pause_args = cb_pause_args
            self._cb_unpause_args = cb_unpause_args
            self._cb_end_min_args = cb_end_min_args
            self._cb_end_max_args = cb_end_max_args
            self._cb_cancel_args = cb_cancel_args

            self._was_started = False
            self._was_canceled = False
            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False
            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0

            self._task = None
            self._manager._timers[self._steptimer_id] = self._task

        def start(self):
            """
            Start the step timer. Requires the timer was not started and is not canceled.

            Returns
            -------
            None.

            Raises
            ------
            StepTimerError.AlreadyStartedStepTimerError:
                If the step timer was already started.
            StepTimerError.AlreadyCanceledStepTimerError:
                If the step timer was already canceled.

            """

            if self._was_started:
                raise StepTimerError.AlreadyStartedStepTimerError
            if self._was_canceled:
                raise StepTimerError.AlreadyCanceledStepTimerError

            self._was_started = True
            async_function = self._as_timer()
            self._task = asyncio.ensure_future(async_function, loop=self._loop)
            self._check_structure()

        def pause(self):
            """
            Pause the step timer. Requires the timer was started, is not canceled nor paused.

            Returns
            -------
            None.

            Raises
            ------
            StepTimerError.NotStartedStepTimerError:
                If the step timer was not started yet.
            StepTimerError.AlreadyCanceledStepTimerError:
                If the step timer was already canceled.
            StepTimerError.AlreadyPausedStepTimerError:
                If the step timer was already paused.

            """

            if not self._was_started:
                raise StepTimerError.NotStartedStepTimerError
            if self._was_canceled:
                raise StepTimerError.AlreadyCanceledStepTimerError
            if self._is_paused:
                raise StepTimerError.AlreadyPausedStepTimerError

            self._is_paused = True
            self._asyncio_cancel()
            self._check_structure()

        def unpause(self):
            """
            Unpause the step timer. Requires the timer was started, is not canceled and is paused.

            Returns
            -------
            None.

            Raises
            ------
            StepTimerError.NotStartedStepTimerError:
                If the step timer was not started yet.
            StepTimerError.AlreadyCanceledStepTimerError:
                If the step timer was already canceled.
            StepTimerError.NotPausedStepTimerError:
                If the step timer was not paused.

            """

            if not self._was_started:
                raise StepTimerError.NotStartedStepTimerError
            if self._was_canceled:
                raise StepTimerError.AlreadyCanceledStepTimerError
            if not self._is_paused:
                raise StepTimerError.NotPausedStepTimerError

            self._is_paused = False
            self._just_unpaused = True
            self._asyncio_cancel()
            self._check_structure()

        def cancel(self, set_was_canceled=True):
            """
            Cancel the step timer. Requires the timer not be canceled already.

            Arguments
            ---------
            set_was_canceled : bool
                Mark self._was_canceled to this. Set this to False only if the cancellation is
                'temporary' and the timer is meant to continue. Defaults to True.

            Returns
            -------
            None.

            Raises
            -------
            StepTimerError.AlreadyCanceledStepTimerError:
                If the step timer was already canceled.

            """

            self._was_canceled = True
            self._asyncio_cancel()
            self._check_structure()

        def _asyncio_cancel(self):
            self._task.cancel()
            asyncio.ensure_future(self.await_cancellation(self._task))

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
            if not 0 <= self._min_timer_value:
                err = (f'Expected the steptimer minimum timer value be a non-negative number, '
                       f'found it was {self._min_timer_value} instead.')
                raise AssertionError(err)
            if not self._min_timer_value <= self._timer_value:
                err = (f'Expected the steptimer timer value be at least the minimum timer value '
                       f'{self._min_timer_value}, found it was {self._timer_value} instead.')
                raise AssertionError(err)
            if not self._timer_value <= self._max_timer_value:
                err = (f'Expected the steptimer timer value be at most the maximum timer value '
                       f'{self._max_timer_value}, found it was {self._timer_value} instead.')
                raise AssertionError(err)

            # 2.
            if not 0 < self._firing_interval:
                err = (f'Expect the firing interval be a positive number, found it was '
                       '{self._firing_interval} instead.')
                raise AssertionError(err)

        async def _no_action():
            """
            Dummy function that does nothing.

            Returns
            -------
            None.

            """

            await asyncio.sleep(0)

        async def await_cancellation(self, old_task):
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

        async def _cb_start_fn(self, *args):
            """
            Async function that is executed once: when the steptimer is started.

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the start async function.

            Returns
            -------
            None.

            """

            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0
            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False
            log_print('Started timer {}'.format(self._steptimer_id))

        async def _cb_firing_fn(self, *args):
            """
            Async function that is executed every time the steptimer is updated due to its firing
            interval elapsing.

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the firing async function.

            Returns
            -------
            None.

            """

            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0
            log_print('Timer {} ticked to {}'.format(self._steptimer_id, self._timer_value))
            await asyncio.sleep(self._firing_interval)

        async def _cb_pause_fn(self, *args):
            """
            Async function that is executed every time the steptimer is paused.

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the pause async function.

            Returns
            -------
            None.

            """

            self._subtimestep_elapsed += time.time() - self._last_timestep_time
            log_print('Timer {} paused at {}'.format(self._steptimer_id, self._timer_value))
            await asyncio.sleep(self._firing_interval)

        async def _cb_unpause_fn(self, *args):
            """
            Async function that is executed every time the steptimer is unpaused.

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the unpause async function.

            Returns
            -------
            None.

            """

            adapted_firing_interval = max(0, self._firing_interval - self._subtimestep_elapsed)
            self._last_timestep_time = time.time()
            log_print('Timer {} unpaused from {}'.format(self._steptimer_id, self._timer_value))
            await asyncio.sleep(adapted_firing_interval)

        async def _cb_end_min_fn(self, *args):
            """
            Async function that is executed once: once the steptimer time ticks DOWN to at most the
            steptimer minimum timer value.

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the end by minimum async function.

            Returns
            -------
            None.

            """

            log_print('Timer {} min-ended at {}'.format(self._steptimer_id, self._timer_value))
            pass

        async def _cb_end_max_fn(self, *args):
            """
            Async function that is executed once: once the steptimer time ticks UP to at least the
            steptimer maximum timer value.

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the end by maximum async function.

            Returns
            -------
            None.

            """

            log_print('Timer {} max-ended at {}'.format(self._steptimer_id, self._timer_value))
            pass

        async def _cb_cancel_fn(self, *args):
            """
            Async function that is executed once: once the steptimer is canceled (more precisely,
            after the steptimer retrieves the cancellation error).

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the cancellation async function.

            Returns
            -------
            None.

            """

            log_print('Timer {} canceled at {}'.format(self._steptimer_id, self._timer_value))
            pass

        async def _as_timer(self):
            """
            Async function rerpresenting the steptimer visible timer.

            Returns
            -------
            None.

            """
            await self._cb_start_fn(*self._cb_start_args)

            while True:
                try:
                    # If a timestep just finished without any interruptions
                    if (not self._is_paused and not self._just_unpaused):
                        self._just_paused = False
                        await self._cb_firing_fn(*self._cb_firing_args)
                    # If a timestep was just unpaused
                    elif (not self._is_paused and self._just_unpaused):
                        self._just_paused = False
                        self._just_unpaused = False
                        await self._cb_unpause_fn(*self._cb_unpause_args)
                    # Otherwise, timer is paused, wait timestep miliseconds again
                    else:
                        await asyncio.sleep(self._timestep_length)
                except asyncio.CancelledError:
                    # Code can run here for one of two reasons
                    # 1. The timer was canceled
                    # 2. The timer was just unpaused after waiting at least one loop
                    # 2. The timer was just paused
                    if self._was_canceled:
                        await self._cb_cancel_fn(*self._cb_cancel_args)
                        break
                    elif self._just_unpaused:
                        pass
                    else:
                        self._just_paused = True
                        try:
                            await self._cb_pause_fn(*self._cb_pause_args)
                        except asyncio.CancelledError:
                            # This would be triggered only as a result of .unpause()
                            pass
                else:
                    if (not self._is_paused and not self._just_unpaused):
                        self._timer_value += self._timestep_length

                        # Check if timer has gone beyond limits, and end or bound it appropriately
                        if self._timer_value <= self._min_timer_value:
                            self._timer_value = self._min_timer_value
                            if self._timestep_length < 0:
                                await self._cb_end_min_fn(*self._cb_end_min_args)
                                break
                        elif self._timer_value >= self._max_timer_value:
                            self._timer_value = self._max_timer_value
                            if self._timestep_length > 0:
                                await self._cb_end_max_fn(*self._cb_end_max_args)
                                break

    def __init__(self):
        self._timers = dict()

