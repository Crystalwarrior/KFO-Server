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
Module that contains the Timer and TimerManager classes.
"""

import asyncio
import time

from server.constants import Constants
from server.exceptions import TimerError

class Timer:
    """
    A mutable data type for timers. A timer is a measurer of some internal time with a time
    manager. This internal time can be adjusted to tick at any non-zero custom rates including
    but not limited to

    * 1 internal second per real second (equivalent rate as a chronometer).
    * -1 internal second per real second (equivalent rate as a countdown clock).
    * 0.5 internal seconds per real second (equivalent rate as a chronometer running at half \
    real time speed).
    * -2 internal seconds per real second (equivalent rate as a countdown clock running twice the \
    real time speed).

    This internal time can be consulted at any time and will always be lower bounded by some
    timer minimum value and upper bounded by some timer maximum value. It can also be set to some
    specific value or changed by some amount of time at any time, but if it happens the new internal
    timer goes below the timer minimum value, it will set itself to the minimum value (a similar
    event happens if the new internal timer goes above the timer maximum value). This internal time
    is updated as often as the OS allows. This minimum value must be at least 0 (the internal timer
    may not become negative).

    A timer when initialized does not start automatically, but once it starts, it will tick at the
    rate described previously. This tick rate can be adjusted at any moment, so that immediately
    after the adjustment the internal timer ticks at that new rate. Once started a timer cannot be
    started again.

    A timer can be paused, so that the internal timer will stop changing. It can also be unpaused,
    so the internal timer will start changing again by the previously described rules. Attempting
    to pause a timer that was not started does nothing. Unpausing a timer that was not started
    starts it. A timer that is paused cannot be paused again, and a timer that was started and is
    not unpaused cannot be unpaused again.

    A timer can be terminated, so that the internal timer will stop changing. A timer that was
    terminated may not be started, paused, unpaused or terminated again. A timer also has an
    'auto destroy' flag, which if set to true, will also request the manager of the timer delete
    it from its list of timers as well after the timer was terminated.

    If the tick rate is positive and the internal time reaches the timer maximum value, it is said
    it has max-ended; similarly if the tick rate is negative and the internal time reaches the
    timer minimum value, it is said it has min-ended. Once a timer has max-ended, or min-ended,
    one of the following events takes place

    * If the timer was set to 'auto reset', the internal time will be adjusted to the timer \
    minimum value if the tick rate was positive and the maximum one if the tick rate was negative.
    * Otherwise, if the timer was set to 'auto destroy', it will automatically terminate itself \
    and, if the 'auto destroy' flag was set, it will request its manager delete it from its list \
    of timers.

    A timer allows the implementation different callback functions that will be executed on the
    following events:

    * When the internal timer ends automatically by min-ending.
    * When the internal timer ends automatically by max-ending.
    * When the internal timer is internally updated (although you should not put computationally \
    expensive functions here due to this callback being constantly executed).

    Overwritable Methods
    --------------------
    _on_min_end :
        Callback function to be executed if the timer's internal timer ticks down to or
        below its minimum timer value.
    _on_max_end :
        Callback function to be executed if the timer's internal timer ticks up to or
        above its maximum timer value.
    _on_refresh :
        Callback function to be executed every time the internal timer updates itself.

    Class Attributes
    ----------------
    DEF_START_TIMER_VALUE : float
        Default start value in internal seconds of the internal timer of all timers of this type.
    DEF_MIN_TIMER_VALUE : float
        Default minimum value in internal seconds of the internal timer of all timers of this type.
    DEF_MAX_TIMER_VALUE : float
        Default maximum value in internal seconds the internal timer of all timers of this type.
    DEF_TICK_RATE : float
        Default rate in internal seconds/IRL seconds at which the internal timer will tick.

    """

    # (Private) Attributes
    # --------------------
    # _server : TsuserverDR
    #     Server the timer belongs to.
    # _manager : TimerManager
    #     Manager for this timer.
    # _timer_id : str
    #     Identifier for this timer.
    # _tick_rate : float
    #     Rate in internal seconds/IRL seconds at which the internal timer ticks.
    # _base_value : float
    #     Number of internal seconds to add onto the real seconds elapsed per tick rate map
    #     to compute the proper internal time.
    # _last_time_update : float or None
    #     If None, the timer was not started. Otherwise, it is the last time the internal timer was
    #     updated in seconds; no base value for this can be assumed, so only differences between
    #     these values are meaningful.
    # _min_value : float
    #     Minimum value the internal timer may take. If the timer ticks below this, it will end
    #     or restart automatically.
    # _max_value : float
    #     Maximum value the internal timer may take. If the timer ticks above this, it will end
    #     or restart automatically.
    # _auto_restart : bool
    #     If True, the internal time will be reset to the min value if the tick rate is positive
    #     and the timer max-ended, or to the max value if the tick rate is negative and the timer
    #     min-ended. Otherwise, either of those situations will make the timer end automatically.
    # _auto_destroy : bool
    #     If True, if the timer ends automatically, it will also make its manager delete it from
    #     its list of timers. Otherwise, no such action is performed.
    # _elapsed_per_tick_rate : dict of float to float
    #     For each (tick, elapsed) (key, value) pair in the dictionary, it represents the number
    #     of real seconds elapsed while the timer had that tick rate and was not paused.
    # _started : bool
    #     True if the internal timer was ever started, False otherwise.
    # _paused : bool
    #     True if the internal timer is paused, False otherwise.
    # _terminated : bool
    #     True if the timer was terminated, False otherwise.
    # _task : asyncio.Task or None
    #     Actual timer task. _task is None as long as the timer is not started.

    # Invariants
    # ----------
    # 1. `0 <= self._min_value <= self.get() <= self._max_value`
    # 2. `0 <= self.DEF_MIN_TIMER_VALUE <= self.DEF_START_TIMER_VALUE <= self.DEF_MAX_TIMER_VALUE`
    # 3. `self.tick_rate != 0`

    DEF_START_TIMER_VALUE = 0
    DEF_MIN_TIMER_VALUE = 0
    DEF_MAX_TIMER_VALUE = 60*60*6 # 6 hours in seconds
    DEF_TICK_RATE = 1 # Tick up 1 second per second

    def __init__(self, server, manager, timer_id, tick_rate=None, start_value=None, min_value=None,
                 max_value=None, auto_restart=False, auto_destroy=True):
        """
        Create a new timer.

        Parameters
        ----------
        server : TsuserverDR
            Server the timer belongs to.
        manager : TimerManager
            Manager for this timer.
        timer_id : str
            Identifier for this timer.
        start_value : float, optional
            Number of seconds in the apparent timer when it is created. Defaults to None
            (and then set to self.DEF_START_TIMER_VALUE).
        tick_rate : float, optional
            Starting rate in timer seconds/IRL seconds at which the timer will tick. Defaults to
            None (and then set to self.DEF_TICK_RATE).
        min_timer_value : float, optional
            Minimum value the internal timer may take. If the internal timer ticks below this,
            it will terminate or restart automatically. It must be a non-negative number.
            Defaults to None (and then set to self.DEF_MIN_TIMER_VALUE).
        max_timer_value : float, optional
            Maximum value the internal timer may take. If the internal timer ticks above this,
            it will terminate or restart automatically. Defaults to None (and then set to
            self.DEF_MAX_TIMER_VALUE).
        auto_restart : bool
            If True, the internal time will be reset to the min value if the tick rate is positive
            and the timer max-ended, or to the max value if the tick rate is negative and the timer
            min-ended. Otherwise, either of those situations will make the timer end automatically.
            Defaults to False.
        auto_destroy : bool
            If True, if the timer ends automatically, it will also make its manager delete it from
            its list of timers. Otherwise, no such action is performed. Defaults to True.

        Raises
        ------
        TimerError.TimerTooLowError
            If `timer_value < min_timer_value`
        TimerError.TimerTooHighError
            If `timer_value > max_timer_value`
        TimerError.InvalidMinTimerValueError
            If `min_timer_value < 0`
        TimerError.InvalidTickRateError
            If `tick_rate == 0`

        Returns
        -------
        None.

        """

        if tick_rate is None:
            tick_rate = self.DEF_TICK_RATE
        if start_value is None:
            start_value = self.DEF_START_TIMER_VALUE
        if min_value is None:
            min_value = self.DEF_MIN_TIMER_VALUE
        if max_value is None:
            max_value = self.DEF_MAX_TIMER_VALUE

        if start_value < min_value:
            raise TimerError.TimerTooLowError
        if start_value > max_value:
            raise TimerError.TimerTooHighError
        if min_value < 0:
            raise TimerError.InvalidMinTimerValueError
        if tick_rate == 0:
            raise TimerError.InvalidTickRateError

        self._server = server
        self._manager = manager
        self._id = timer_id

        self._tick_rate = tick_rate
        self._base_value = start_value
        self._last_time_update = None
        self._min_value = min_value
        self._max_value = max_value
        self._auto_restart = auto_restart
        self._auto_destroy = auto_destroy

        self._elapsed_per_tick_rate = dict()
        self._started = False
        self._paused = False
        self._terminated = False

        self._internal_timer_task = None

    def get_id(self) -> str:
        """
        Return the ID of the timer.

        Returns
        -------
        str
            ID of the timer.

        """

        return self._id

    def started(self) -> bool:
        """
        Return if the timer was started.

        Returns
        -------
        bool
            True if started, False otherwise.

        """

        return self._started

    def start(self) -> float:
        """
        Start the timer if it was not started or terminated previously.

        Raises
        ------
        TimerError.AlreadyStartedTimerError
            If the timer was already started.
        TimerError.AlreadyTerminatedTimerError
            If the timer was already terminated.

        Returns
        -------
        float
            Current internal time (in internal seconds).

        """

        if self._started:
            raise TimerError.AlreadyStartedTimerError
        if self._terminated:
            raise TimerError.AlreadyTerminatedTimerError

        self._started = True
        self._last_time_update = time.perf_counter()

        self._internal_timer_task = Constants.create_fragile_task(self._internal_timer())
        # print(f'[{time.time()}] Timer {self.get_id()} started at {self._base_value}.')
        self._check_structure()

        return self._base_value # This is the current internal time, as no seconds have passed.

    def get(self) -> float:
        """
        Return the current internal timer.

        Returns
        -------
        float
            Current internal time (in internal seconds).

        """

        current_time = self._get()
        self._check_structure()
        return current_time

    def _get(self) -> float:
        """
        Helper function for self.get that does the heavy work without calling self._check_structure

        Returns
        -------
        float
            Current internal time (in internal seconds).

        """

        current_time = self._base_value
        self._update_elapsed_per_tick()

        for (tick_rate, elapsed) in self._elapsed_per_tick_rate.items():
            current_time += tick_rate*elapsed
        if current_time >= self._max_value:
            current_time = self._max_value
        if current_time <= self._min_value:
            current_time = self._min_value
        return current_time

    def terminated(self):
        """
        Return if the timer was terminated.

        Returns
        -------
        bool
            True if terminated, False otherwise.

        """
        return self._terminated

    def terminate(self) -> float:
        """
        Terminate the timer if it was not terminated already.

        Raises
        ------
        TimerError.AlreadyTerminatedTimerError
            If the timer was already terminated.

        Returns
        -------
        float
            Internal time at the time of termination.

        """

        if self._terminated:
            raise TimerError.AlreadyTerminatedTimerError

        # Fetch current time to return later.
        current_time = self._get()

        self._terminated = True
        if self._internal_timer_task:
            Constants.cancel_and_await_task(self._internal_timer_task)
        # The if is false iff the timer was not started

        if self._auto_destroy:
            try:
                self._manager.delete_timer(self)
            except TimerError.ManagerDoesNotManageTimerError:
                # This should only happen if the .terminate call came from a call to manager's
                # .delete_timer, at which point it is meaningless to attempt to make the manager
                # attempt to delete the timer, it is already gone.
                pass

        self._check_structure()
        return current_time

    def get_tick_rate(self) -> float:
        """
        Get the tick rate of the timer.

        Returns
        -------
        float
            Tick rate of the timer in internal seconds/IRL seconds.

        """

        return self._tick_rate

    def set_tick_rate(self, new_tick_rate):
        """
        Set the new tick rate of the timer

        Parameters
        ----------
        new_tick_rate : float
            New tick rate in internal seconds/IRL seconds.

        Raises
        ------
        TimerError.InvalidTickRateError:
            If the new tick rate is 0.

        Returns
        -------
        None.

        """

        if new_tick_rate == 0:
            raise TimerError.InvalidTickRateError

        # print(f'{time.time()} Timer {self._id} set tick to {new_tick_rate} at {self.get()}')
        self._tick_rate = new_tick_rate
        self._check_structure()

    def paused(self):
        """
        Return if the timer is paused.

        Returns
        -------
        bool
            True if the timer was paused, False otherwise.

        """
        return self._paused

    def pause(self) -> float:
        """
        If the timer was not started, return the current internal time. Otherwise, if it was not
        paused, pause the timer so that it is no longer updated and return the internal time at
        the time of the pausing.

        Raises
        ------
        TimerError.AlreadyPausedTimerError
            If the timer was already paused.
        TimerError.AlreadyTerminatedTimerError
            If the timer was already terminated.

        Returns
        -------
        float
            Current internal time.

        """

        if self._paused:
            raise TimerError.AlreadyPausedTimerError
        if self._terminated:
            raise TimerError.AlreadyTerminatedTimerError
        if not self._started:
            return self._base_value

        self._paused = True
        current_time = self._get()
        # print(f'{time.time()} Timer {self._id} paused at {current_time}')
        self._check_structure()

        return current_time

    def unpause(self) -> float:
        """
        If the timer was not started, start it and return the current internal time. Otherwise, if
        it was paused, unpause the timer so that it will resume ticking and return the internal
        time at the time of the unpausing.

        Raises
        ------
        TimerError.NotPausedTimerError
            If the timer was started and already not paused.
        TimerError.AlreadyTerminatedTimerError
            If the timer was already terminated.

        Returns
        -------
        float
            Current internal time.

        """
        if self._started and not self._paused:
            raise TimerError.NotPausedTimerError
        if self._terminated:
            raise TimerError.AlreadyTerminatedTimerError
        if self._started:
            current_time = self._get()
            # Put _paused after getting time, so that the timer is updated as if it was paused still
            # and thus does not consider the time spent while paused as time elapsed
            self._paused = False
            # print(f'{time.time()} Timer {self._id} unpaused at {current_time}')
            self._check_structure()
        else:
            current_time = self._base_value
            self.start()

        return current_time

    def set_time(self, new_time: float) -> float:
        """
        Set the current time of the timer to a specific value. If it is below the timer minimum
        value, it is set to the minimum value; if it is above the timer maximum value, it is set
        to the maximum value.

        Parameters
        ----------
        new_time : float
            New internal timer (in internal seconds).

        Returns
        -------
        float
            New internal timer (in internal seconds), bounded appropriately if needed.

        """

        new_time = self._set_time(new_time)
        self._check_structure()
        return new_time

    def _set_time(self, new_time: float) -> float:
        """
        Helper function for self.set_time that does the heavy work without calling
        self._check_structure

        Returns
        -------
        float
            New internal timer (in internal seconds), bounded appropriately if needed.

        """

        new_time = max(self._min_value, min(self._max_value, new_time))
        self._base_value = new_time
        self._elapsed_per_tick_rate = dict()
        self._last_time_update = time.perf_counter()
        return new_time

    def change_time_by(self, delta: float) -> float:
        """
        Change the current time of the timer by some value. If the new time  is below the timer
        minimum value, it is set to the minimum value; if it is above the timer maximum value, it
        is set to the maximum value.

        Parameters
        ----------
        delta : float
            Value to change the current time by (in internal seconds).

        Returns
        -------
        float
            New internal timer (in internal seconds), bounded appropriately if needed.

        """

        new_time = self._set_time(self._get() + delta)
        self._check_structure()
        return new_time

    def _on_refresh(self, new_time: float, elapsed: float):
        """
        Callback function that is executed every time the timer is updated.

        Returns
        -------
        None.

        """

        # print(f'{time.time()} Timer {self._id} ticked to {new_time}')

    def _on_min_end(self):
        """
        Callback function that is executed once: once the timer time ticks DOWN to at most
        the timer minimum timer value.

        If the timer was an auto restart one, the current time will be self._min_value and the timer
        will not be terminated; otherwise it will be self._max_value and be terminated.

        If the timer had auto destroy on and the timer was terminated, by the time it executes
        code here, the manager will have already deleted the timer.

        Returns
        -------
        None.

        """

        # print(f'[{time.time()}] Timer {self.get_id()} min-ended at {self.get()}')

    def _on_max_end(self):
        """
        Callback function that is executed once: once the timer time ticks UP to at least
        the timer maximum timer value.

        If the timer was an auto restart one, the current time will be self._max_value and the timer
        will not be terminated; otherwise it will be self._min_value and be terminated.

        If the timer had auto destroy on and the timer was terminated, by the time it executes
        code here, the manager will have already deleted the timer.

        Returns
        -------
        None.

        """

        # print(f'[{time.time()}] Timer {self.get_id()} max-ended at {self.get()}')

    def _update_elapsed_per_tick(self):
        """
        Update the elapsed per tick rate map with the amount of time elapsed since the last update.

        Returns
        -------
        None.

        """

        if self._last_time_update is None:
            # Timer has not started
            return

        elapsed = time.perf_counter()-self._last_time_update
        self._last_time_update += elapsed

        if self._terminated or self._paused:
            # If terminated and not paused, this should only run if it takes longer for the timer
            # to be terminated than the refresh rate.
            return

        current_tick_rate = self._tick_rate
        if current_tick_rate not in self._elapsed_per_tick_rate:
            self._elapsed_per_tick_rate[current_tick_rate] = 0

        self._elapsed_per_tick_rate[current_tick_rate] += elapsed

    async def _internal_timer(self):
        """
        Task of the internal timer, which handles the logic for pausing, min-ending and max-ending.
        """

        current_time = self._get()
        while True:
            if (self._tick_rate > 0 and current_time >= self._max_value):
                if self._auto_restart:
                    self.set_time(self._min_value)
                    self._on_max_end()
                else:
                    self.terminate()
                    self.set_time(self._max_value)
                    self._on_max_end()
                    break
            if (self._tick_rate <= 0 and current_time <= self._min_value):
                if self._auto_restart:
                    self._set_time(self._max_value)
                    self._on_min_end()
                else:
                    self.terminate()
                    self._set_time(self._min_value)
                    self._on_min_end()
                    break

            await asyncio.sleep(0)
            new_time = self._get()
            elapsed = new_time - current_time
            if elapsed:
                self._on_refresh(new_time, elapsed)
            current_time = new_time

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

        epsilon = 0.001 #  Account for rounding errors and floating point arithmetic
        timer_value = self._get()

        # 1.
        err = (f'Expected the timer minimum timer value be a non-negative number, found '
               f'it was {self._min_value} instead.')
        assert self._min_value >= 0, err

        err = (f'Expected the timer value be at least the minimum timer value '
               f'{self._min_value}, found it was {timer_value} instead.')
        assert timer_value >= self._min_value - epsilon, err

        err = (f'Expected the timer value be at most the maximum timer value '
               f'{self._max_value}, found it was {timer_value} instead.')
        assert timer_value <= self._max_value + epsilon, err

        # 2.
        err = (f'Expected the default timer minimum timer value be a non-negative number, '
               f'found it was {self.DEF_MIN_TIMER_VALUE} instead.')
        assert self.DEF_MIN_TIMER_VALUE >= 0, err

        err = (f'Expected the default timer value be at least the default minimum '
               f'timer value {self.DEF_MIN_TIMER_VALUE}, found it was '
               f'{self.DEF_START_TIMER_VALUE}.')
        assert self.DEF_START_TIMER_VALUE >= self.DEF_MIN_TIMER_VALUE, err

        err = (f'Expected the default timer value be at most the default maximum '
               f'timer value {self.DEF_MAX_TIMER_VALUE}, found it was '
               f'{self.DEF_START_TIMER_VALUE} instead.')
        assert self.DEF_START_TIMER_VALUE <= self.DEF_MAX_TIMER_VALUE, err

        # 3.
        err = 'Expected the tick rate be non-zero, found it was zero.'
        assert self._tick_rate != 0

    def __str__(self):
        """
        Return a string representation of this tutimerner.

        Returns
        -------
        str
            Representation.

        """

        return (f"Timer::{self.get_id()}:{self._get()}"
                f"{self.started()}:{self.paused()}:{self.terminated()}")

    def __repr__(self):
        """
        Return a representation of this timer.

        Returns
        -------
        str
            Printable representation.

        """

        return (f'Timer(server, {self._manager.get_id()}, "{self.get_id()}", '
                f'tick_rate={self._tick_rate}, '
                f'min_value={self._min_value}, '
                f'max_value={self._max_value}, '
                f'auto_restart={self._auto_restart}, '
                f'auto_destroy={self._auto_destroy}) || '
                f'time={self._get()}, '
                f'started={self._started}, '
                f'paused={self._paused}, '
                f'terminated={self._terminated}, '
                f'elapsed_per_tick_rate={self._elapsed_per_tick_rate}')

class TimerManager():
    """
    A mutable data type for a manager for timers in a server.

    The class (with its default implementation) is coroutine-safe as the default timer class
    is coroutine-safe and every other public method of the manager is synchronous.

    The class is NOT thread-safe.

    Overwritable Methods
    --------------------
    get_available_timer_id :
        Generate a new timer ID. Can be modified to provide different timer ID formats.

    """

    # (Private) Attributes
    # --------------------
    # _server : TsuserverDR
    #     Server the timer manager belongs to.
    # _default_timer_type : Timer or functools.partial
    #     The type of timer this timer manager will create by default when ordered to create a new
    #     one.
    # _timer_limit : int or None
    #     If an int, it is the maximum number of timers this manager supports. If None, the
    #     manager may manage an arbitrary number of timers.
    # _id_to_timer : dict of str to self.Steptimer
    #     Mapping of timer IDs to timers that this manager manages.

    # Invariants
    # ----------
    # 1. If `self._timer_limit` is an int, then `len(self._id_to_timer) <=`
    # `self._timer_limit`.
    # 2. For every tuple `(timer_id, timer)` in `self._id_to_group.items()`:
    #     a. `timer._manager = self`.
    #     b. `timer.get_id() = timer_id`.
    # 3. For every pair of distinct timers `timer1` and `timer2` in
    # `self._id_to_timer.values()`:
    #     a. `timer1.get_id() != timer2.get_id()`.

    def __init__(self, server, timer_limit=None, default_timer_type=None):
        """
        Create a timer manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this timer manager belongs to.
        timer_limit : int, optional
            The maximum number of timers this manager can handle. The default is None.
        default_timer_type : Timer, optional
            The default type of timer this manager will create. Defaults to None (and then
            converted to Timer).

        """

        if default_timer_type is None:
            default_timer_type = Timer

        self._server = server
        self._timer_limit = timer_limit
        self._default_timer_type = default_timer_type

        self._id_to_timer = dict()

    def get_id(self):
        """
        Return the ID of this manager. This ID is guaranteed to be unique among
        simultaneously existing managers.

        Returns
        -------
        str
            ID.

        """

        return hex(id(self))

    def new_timer(self, timer_type=None, start_value=None, tick_rate=1,
                  min_value=None, max_value=None, auto_restart=False, auto_destroy=True):
        """
        Create a new timer with given parameters managed by this manager.

        Parameters
        ----------
        timer_type : Timer, optional
            Class of timer that will be produced. Defaults to None (and converted to the
            manager's default timer type).
        start_value : float, optional
            Number of seconds the internal timer the timer will initially have. Defaults to
            None (will use the default from `timer_type`).
        tick_rate : float, optional
            Starting rate in timer seconds/IRL seconds at which the timer will tick. Defaults to
            None (will use the default from `timer_type`).
        min_value : float, optional
            Minimum value the internal timer may take. If the timer ticks below this, it will end
            automatically. It must be a non-negative number. Defaults to None (will use the
            default from `timer_type`.)
        max_value : float, optional
            Maximum value the internal timer may take. If the timer ticks above this, it will end
            automatically. Defaults to None (will use the default from `timer_type`).
        auto_restart : bool, optional
            If True, the timer will reset without terminating back to its max value if the tick rate
            was non-negative and the timer went below its min value, or back to its max value if
            the tick rate was negative and the timer went above its max value. If False, the
            timer will terminate once either of the two conditions is satisfied without restarting.
            Defaults to False.
        auto_destroy : bool, optional
            If True, the manager will automatically delete the timer once it is terminated by
            ticking out or manual termination. If False, no such automatic deletion will take place.
            Defaults to True.

        Returns
        -------
        Timer
            The created timer.

        Raises
        ------
        TimerError.ManagerTooManyTimersError
            If the manager is already managing its maximum number of timers.

        """

        # Check if adding a new timer to manage would be one too many
        if self._timer_limit is not None:
            if len(self._id_to_timer) >= self._timer_limit:
                raise TimerError.ManagerTooManyTimersError

        # Fill in default values
        if timer_type is None:
            timer_type = self._default_timer_type

        # Generate a timer ID and the new timer
        timer_id = self.get_available_timer_id()
        timer = timer_type(self._server, self, timer_id,
                           start_value=start_value,
                           tick_rate=tick_rate,
                           min_value=min_value,
                           max_value=max_value,
                           auto_restart=auto_restart,
                           auto_destroy=auto_destroy,)
        self._id_to_timer[timer_id] = timer

        self._check_structure()
        return timer

    def delete_timer(self, timer):
        """
        Delete a timer managed by this manager, terminating it first if needed.

        Parameters
        ----------
        timer : Timer
            The timer to delete.

        Returns
        -------
        str
            The ID of the timer that was deleted.

        Raises
        ------
        TimerError.ManagerDoesNotManageTimerError
            If the manager does not manage the target timer.

        """

        # Assert timer is managed by manager.
        if not self.manages_timer(timer):
            raise TimerError.ManagerDoesNotManageTimerError

        timer_id = timer.get_id()
        # Pop the timer. By doing this now, it helps guard the class' only call to an
        # asynchronous function. In particular, once .delete_timer() is called on a managed
        # timer, these two lines will always execute, which will prevent the timer to
        # terminate from influencing other public method calls of the manager.
        self._id_to_timer.pop(timer_id)

        try:
            timer.terminate()
        except TimerError.AlreadyTerminatedTimerError:
            pass

        # As the timer is popped, it will no longer be referred to in the internal structure
        # check function.
        self._check_structure()
        return timer_id

    def manages_timer(self, timer):
        """
        Return True if the timer is managed by this manager, False otherwise.

        Parameters
        ----------
        timer : TimerManager.Timer
            The timer to check.

        Returns
        -------
        bool
            True if the manager manages this timer, False otherwise.

        """

        return timer in self._id_to_timer.values()

    def get_timers(self):
        """
        Return (a shallow copy of) the timers this manager manages.

        Returns
        -------
        set of Timer
            Timers this manager manages.

        """

        return set(self._id_to_timer.values())

    def get_timer_limit(self):
        """
        Return the timer limit of this manager.

        Returns
        -------
        int
            Timer limit.

        """

        return self._timer_limit

    def get_timer_by_id(self, timer_id):
        """
        If `timer_tag` is the ID of a timer managed by this manager, return that timer.

        Parameters
        ----------
        timer_id: str
            ID of timer this manager manages.

        Returns
        -------
        Timer
            The timer whose ID matches the given ID.

        Raises
        ------
        TimerError.ManagerInvalidTimerIDError:
            If `timer_id` is not the ID of a timer this manager manages.

        """

        try:
            return self._id_to_timer[timer_id]
        except KeyError:
            raise TimerError.ManagerInvalidTimerIDError

    def get_timer_ids(self):
        """
        Return (a shallow copy of) the IDs of all timers managed by this manager.

        Returns
        -------
        set of str
            The IDs of all managed timers.

        """

        return set(self._id_to_timer.keys())

    def get_available_timer_id(self):
        """
        Get a timer ID that no other timer managed by this manager has.

        Returns
        -------
        str
            A unique timer ID.

        Raises
        ------
        TimerError.ManagerTooManyTimersError
            If the manager is already managing its maximum number of timers.

        """

        timer_number = 0
        while self._timer_limit is None or timer_number < self._timer_limit:
            new_timer_id = "timer{}".format(timer_number)
            if new_timer_id not in self._id_to_timer.keys():
                return new_timer_id
            timer_number += 1
        raise TimerError.ManagerTooManyTimersError

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        if self._timer_limit is not None:
            err = (f'For timer manager {self}, expected that it managed at most '
                   f'{self._timer_limit} timers, but found it managed '
                   f'{len(self._id_to_timer)} timers. || {self}')
            assert len(self._id_to_timer) <= self._timer_limit, err

        # 2.
        for (timer_id, timer) in self._id_to_timer.items():
            # 2a.
            err = (f'For timer manager {self}, expected that its managed timer '
                   f'{timer} recognized that it was managed by it, but found it did not. '
                   f'|| {self}')
            assert timer._manager == self, err

            # 2b.
            err = (f'For timer manager {self}, expected that timer {timer} '
                   f'that appears in the ID to timer mapping has the same ID as in the '
                   f'mapping, but found it did not. || {self}')
            assert timer.get_id() == timer_id, err

        # 3.
        for timer1 in self._id_to_timer.values():
            for timer2 in self._id_to_timer.values():
                if timer1 == timer2:
                    continue

                # 3a.
                err = (f'For timer manager {self}, expected that its two managed timers '
                       f'{timer1}, {timer2} had unique timer IDS, but found '
                       f'they did not. || {self}')
                assert timer1.get_id() != timer2.get_id(), err

        # Last.
        for timer in self._id_to_timer.values():
            timer._check_structure()

    def __repr__(self):
        """
        Return a representation of this timer manager.

        Returns
        -------
        str
            Printable representation.

        """

        return (f"TimerManager(server, timer_limit={self.get_timer_limit()}, "
                f"default_timer_type={self._default_timer_type}, "
                f"|| "
                f"_id_to_timer={self._id_to_timer}, "
                f"id={self.get_id()})")
