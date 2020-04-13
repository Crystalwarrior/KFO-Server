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

A steptimer is a timer with an apparent timer value that ticks up/down a fixed period of time once
every fixed interval (a step). This allows timers that simulate slow downs or fast forwarding (for
example, a timer that ticks down one second once every real 5 seconds).
A steptimer when initialized does not start automatically, but once it starts, it can be paused
(where the apparent timer will not change) and unpaused (where the apparent timer will change by
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
* When the steptimer starts.
* When the steptimer ticks up/down once the interval elapses.
* When the steptimer is paused.
* When the steptimer is unpaused.
* When the steptimer ends automatically by ticking DOWN below 0.
* When the steptimer ends automatically by ticking UP above _MAXIMUM_TIMER_VALUE
* When the steptimer is terminated.
"""

import asyncio
import time

from server.exceptions import StepTimerError
from server.logger import log_print

class StepTimerManager:
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
    _id_to_steptimer : dict of str to self.StepTimer
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

    class StepTimer:
        """
        A mutable data type representing steptimers.
        A steptimer is a timer with an apparent timer value that ticks up/down a fixed period of
        time once every fixed interval (a step).

        Attributes
        ----------
        _server : TsuserverDR
            Server the steptimer belongs to.
        _manager : StepTimerManager
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
        _cb_start_args : tuple
            Arguments to the function called on steptimer start.
        _cb_firing_args : tuple
            Arguments to the function called on steptimer ticking.
        _cb_pause_args : tuple
            Arguments to the function called on steptimer pause.
        _cb_unpause_args : tuple
            Arguments to the function called on steptimer unpause.
        _cb_end_min_args : tuple
            Arguments to the function called on steptimer ticking down below _min_timer_value.
        _cb_end_max_args : tuple
            Arguments to the function called on steptimer ticking up above _max_timer_value.
        _cb_terminate_args : tuple
            Arguments to the function called on steptimer terminated externally.
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

        def __init__(self, server, manager, steptimer_id, timer_value, timestep_length,
                     firing_interval, min_timer_value, max_timer_value, cb_start_args,
                     cb_firing_args, cb_pause_args, cb_unpause_args, cb_end_min_args,
                     cb_end_max_args, cb_terminate_args):
            """
            Create a new steptimer.

            Parameters
            ----------
            server : TsuserverDR
                Server the steptimer belongs to.
            manager : StepTimerManager
                Manager for this steptimer.
            steptimer_id : str
                Identifier for this steptimer.
            timer_value : float
                Number of seconds in the apparent steptimer.
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
                Arguments to the function called on steptimer start. Defaults to an empty tuple.
            cb_firing_args : tuple
                Arguments to the function called on steptimer ticking. Defaults to an empty tuple.
            cb_pause_args : tuple
                Arguments to the function called on steptimer pause. Defaults to an empty tuple.
            cb_unpause_args : tuple
                Arguments to the function called on steptimer unpause. Defaults to an empty tuple.
            cb_end_min_args : tuple
                Arguments to the function called on steptimer ticking down below _min_timer_value.
                Defaults to an empty tuple.
            cb_end_max_args : tuple
                Arguments to the function called on steptimer ticking up above _max_timer_value.
                Defaults to an empty tuple.
            cb_terminate_args : tuple
                Arguments to the function called on steptimer terminated externally. Defaults to an
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
            self._cb_terminate_args = cb_terminate_args

            self._was_started = False
            self._was_terminated = False
            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False
            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0

            # This task will be an _as_timer coroutine that is meant to emulate the apparent timer.
            # This task will frequently be canceled for the purposes of updating the timer on user
            # request, or for the purposes of pausing and unpausing, and thus terminations will be
            # supprosed. The only way asyncio.CancelledError will not be ignored is via the apparent
            # timer ticking up beyond its maximum or down beyond its minimum, or via .terminate()
            self._task = None

        def start(self):
            """
            Start the steptimer. Requires the timer was not started and is not terminated.

            Returns
            -------
            None.

            Raises
            ------
            StepTimerError.AlreadyStartedStepTimerError:
                If the steptimer was already started.
            StepTimerError.AlreadyTerminatedStepTimerError:
                If the steptimer was already terminated.

            """

            if self._was_started:
                raise StepTimerError.AlreadyStartedStepTimerError
            if self._was_terminated:
                raise StepTimerError.AlreadyTerminatedStepTimerError

            self._was_started = True
            async_function = self._as_timer()
            self._task = asyncio.ensure_future(async_function)
            self._check_structure()

        def pause(self):
            """
            Pause the steptimer. Requires the timer was started, is not terminated nor paused.

            Returns
            -------
            None.

            Raises
            ------
            StepTimerError.NotStartedStepTimerError:
                If the steptimer was not started yet.
            StepTimerError.AlreadyTerminatedStepTimerError:
                If the steptimer was already terminated.
            StepTimerError.AlreadyPausedStepTimerError:
                If the steptimer was already paused.

            """

            if not self._was_started:
                raise StepTimerError.NotStartedStepTimerError
            if self._was_terminated:
                raise StepTimerError.AlreadyTerminatedStepTimerError
            if self._is_paused:
                raise StepTimerError.AlreadyPausedStepTimerError

            self._is_paused = True
            self._refresh()
            self._check_structure()

        def unpause(self):
            """
            Unpause the steptimer. Requires the timer was started, is not terminated and is paused.

            Returns
            -------
            None.

            Raises
            ------
            StepTimerError.NotStartedStepTimerError:
                If the steptimer was not started yet.
            StepTimerError.AlreadyTerminatedStepTimerError:
                If the steptimer was already terminated.
            StepTimerError.NotPausedStepTimerError:
                If the steptimer was not paused.

            """

            if not self._was_started:
                raise StepTimerError.NotStartedStepTimerError
            if self._was_terminated:
                raise StepTimerError.AlreadyTerminatedStepTimerError
            if not self._is_paused:
                raise StepTimerError.NotPausedStepTimerError

            self._is_paused = False
            self._just_unpaused = True
            self._refresh()
            self._check_structure()

        def terminate(self):
            """
            Terminate the steptimer. Requires the timer not be terminated already.

            Returns
            -------
            None.

            Raises
            -------
            StepTimerError.AlreadyTerminatedStepTimerError:
                If the steptimer was already terminated.

            """

            self._was_terminated = True
            self._refresh()
            self._check_structure()

        def get(self):
            return self._timer_value + self._get_subtimestep_elapsed()

        def _refresh(self):
            """
            Interrupt the current timestep with a cancellation order. If the timer was not
            started or was already terminated, this function does nothing.

            Returns
            -------
            None.

            """

            if not self._task:
                return

            self._task.cancel()
            asyncio.ensure_future(self.await_cancellation(self._task))

        def _get_subtimestep_elapsed(self):
            """
            Return the apparent length of time that has elapsed since the latest current timestep
            began or the last time the apparent timer was paused, whichever came later.

            Returns
            -------
            subtimestep : float
                Apparent length of time.

            """

            # If the timer is paused but was not just paused, this is just
            # self._subtimestep_elapsed
            if self._is_paused and not self._just_paused:
                return self._subtimestep_elapsed

            # Otherwise, this is constantly changing
            # so find real time elapsed since last update to subtimestep_elapsed,
            # then adapt to step length
            subtimestep = (time.time() - self._last_timestep_time)
            subtimestep *= self._firing_interval/self._timestep_length
            return self._subtimestep_elapsed + subtimestep

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
                err = (f'Expected the firing interval be a positive number, found it was '
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

            log_print('Timer {} ticked to {}'.format(self._steptimer_id, self._timer_value))

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

            log_print('Timer {} paused at {}'.format(self._steptimer_id, self._timer_value))

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

            log_print('Timer {} unpaused from {}'.format(self._steptimer_id, self._timer_value))

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

        async def _cb_terminate_fn(self, *args):
            """
            Async function that is executed once: once the steptimer is terminated.

            Parameters
            ----------
            *args : Any
                Optional arguments to pass to the termination async function.

            Returns
            -------
            None.

            """

            log_print('Timer {} terminated at {}'.format(self._steptimer_id, self._timer_value))
            pass

        async def _as_timer(self):
            """
            Async function rerpresenting the steptimer visible timer.

            Returns
            -------
            None.

            """

            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0
            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False
            await self._cb_start_fn(*self._cb_start_args)

            while True:
                try:
                    self._just_paused = False
                    # If a timestep just finished without any interruptions
                    if (not self._is_paused and not self._just_unpaused):
                        self._last_timestep_time = time.time()
                        self._subtimestep_elapsed = 0
                        await self._cb_firing_fn(*self._cb_firing_args)
                        await asyncio.sleep(self._firing_interval)
                    # If a timestep was just unpaused
                    elif (not self._is_paused and self._just_unpaused):
                        self._just_unpaused = False
                        adapted_interval = max(0, self._firing_interval-self._subtimestep_elapsed)
                        self._last_timestep_time = time.time()
                        await self._cb_unpause_fn(*self._cb_unpause_args)
                        await asyncio.sleep(adapted_interval)
                    # Otherwise, timer is paused, wait timestep miliseconds again
                    else:
                        await asyncio.sleep(self._firing_interval)
                except asyncio.CancelledError:
                    # Code can run here for one of the following reasons
                    # 1. The timer was terminated
                    # 2. The timer was just unpaused
                    # 3. The timer was just paused
                    if self._was_terminated:
                        await self._cb_terminate_fn(*self._cb_terminate_args)
                        break
                    elif self._just_unpaused:
                        pass
                        # The unpause code is deliberately left within the try to simplify logic
                        # With the pass we immediately go to the unpause code.
                    else:
                        self._just_paused = True
                        self._subtimestep_elapsed += self._get_subtimestep_elapsed()
                        await self._cb_pause_fn(*self._cb_pause_args)
                else:
                    # If we made it here, we made it hrough a timestep without an order to pause,
                    # unpause or terminate in it.
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
                      min_timer_value=_DEF_MIN_TIMER_VALUE, max_timer_value=_DEF_MAX_TIMER_VALUE,
                      cb_start_args=tuple(), cb_firing_args=tuple(),
                      cb_pause_args=tuple(), cb_unpause_args=tuple(),
                      cb_end_min_args=tuple(), cb_end_max_args=tuple(),
                      cb_terminate_args=tuple()):
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
        cb_start_args : tuple
            Arguments to the function called on steptimer start. Defaults to an empty tuple.
        cb_firing_args : tuple
            Arguments to the function called on steptimer ticking. Defaults to an empty tuple.
        cb_pause_args : tuple
            Arguments to the function called on steptimer pause. Defaults to an empty tuple.
        cb_unpause_args : tuple
            Arguments to the function called on steptimer unpause. Defaults to an empty tuple.
        cb_end_min_args : tuple
            Arguments to the function called on steptimer ticking down below _min_timer_value.
            Defaults to an empty tuple.
        cb_end_max_args : tuple
            Arguments to the function called on steptimer ticking up above _max_timer_value.
            Defaults to an empty tuple.
        cb_terminate_args : tuple
            Arguments to the function called on steptimer terminated externally. Defaults to an
            empty tuple.

        Returns
        -------
        self.StepTimer
            The created steptimer.

        Raises
        ------
        StepTimerError.ManagerTooManyStepTimersError
            If the manager is already managing its maximum number of steptimers.
        """

        if self._steptimer_limit is not None:
            if len(self._id_to_steptimer) >= self._steptimer_limit:
                raise StepTimerError.ManagerTooManyStepTimersError

        # Generate a steptimer ID and the new steptimer
        steptimer_id = self._make_new_steptimer_id()
        steptimer = self.StepTimer(self._server, self, steptimer_id, timer_value, timestep_length,
                                   firing_interval, min_timer_value, max_timer_value, cb_start_args,
                                   cb_firing_args, cb_pause_args, cb_unpause_args, cb_end_min_args,
                                   cb_end_max_args, cb_terminate_args)
        self._id_to_steptimer[steptimer_id] = steptimer

        self._check_structure()
        return steptimer

    def delete_steptimer(self, steptimer):
        """
        Delete a steptimer managed by this manager, terminateing it first if needed.

        Parameters
        ----------
        steptimer : self.StepTimer
            The steptimer to delete.

        Returns
        -------
        str
            The ID of the steptimer that was disbanded.

        Raises
        ------
        StepTimerError.ManagerDoesNotManageStepTimerError
            If the manager does not manage the target steptimer

        """

        steptimer_id = self.get_steptimer_id(steptimer) # Assert steptimer is managed by manager
        self._id_to_steptimer.pop(steptimer_id)
        try:
            steptimer.terminate()
        except StepTimerError.AlreadyTerminatedStepTimerError:
            pass

        self._check_structure()
        return steptimer_id

    def get_managed_steptimers(self):
        """
        Return (a shallow copy of) the steptimer this manager manages.

        Returns
        -------
        set of self.StepTimer
            Steptimers this manager manages.

        """

        return set(self._id_to_steptimer.values())

    def get_steptimer(self, steptimer_tag):
        """
        If `steptimer_tag` is a steptimer managed by this manager, return it.
        If it is a string and the ID of a steptimer managed by this manager, return that.

        Parameters
        ----------
        steptimer_tag: self.StepTimer or str
            Steptimers this manager manages.

        Raises
        ------
        StepTimerError.ManagerDoesNotManageStepTimerError:
            If `steptimer_tag` is a steptimer this manager does not manage.
        StepTimerError.ManagerInvalidIDError:
            If `steptimer_tag` is a str and it is not the ID of a steptimer this manager manages.

        Returns
        -------
        StepTimer
            The steptimer that matches the given tag.

        """

        # Case Steptimer
        if isinstance(steptimer_tag, self.StepTimer):
            if steptimer_tag not in self._id_to_steptimer.values():
                raise StepTimerError.ManagerDoesNotManageStepTimerError
            return steptimer_tag

        # Case StepTimer ID
        if isinstance(steptimer_tag, str):
            try:
                return self._id_to_steptimer[steptimer_tag]
            except KeyError:
                raise StepTimerError.ManagerInvalidIDError

        # Every other case
        raise StepTimerError.ManagerInvalidIDError

    def get_steptimer_id(self, steptimer_tag):
        """
        If `steptimer_tag` is the ID of a steptimer managed by this manager, return it.
        If it is a steptimer managed by this manager, return its ID.

        Parameters
        ----------
        steptimer_tag : StepTimer or str
            Steptimer this manager manages.

        Raises
        ------
        StepTimerError.ManagerDoesNotManageStepTimerError:
            If `steptimer_tag` is a steptimer this manager does not manage.
        StepTimerError.ManagerInvalidIDError:
            If `steptimer_tag` is a str and it is not the ID of a steptimer this manager manages.

        Returns
        -------
        StepTimer
            The ID of the steptimer that matches the given tag.

        """

        # Case Steptimer
        if isinstance(steptimer_tag, self.StepTimer):
            if steptimer_tag not in self._id_to_steptimer.values():
                raise StepTimerError.ManagerDoesNotManageStepTimerError
            return steptimer_tag._steptimer_id

        # Case Steptimer ID
        if isinstance(steptimer_tag, str):
            try:
                return self._id_to_steptimer[steptimer_tag]._steptimer_id
            except KeyError:
                raise StepTimerError.ManagerInvalidIDError

        # Every other case
        raise StepTimerError.ManagerInvalidIDError

    def _make_new_steptimer_id(self):
        """
        Generate a steptimer ID that no other steptimer managed by this manager has.

        Raises
        ------
        StepTimerError.ManagerTooManyStepTimersError
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
        else:
            raise StepTimerError.ManagerTooManyStepTimersError

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
