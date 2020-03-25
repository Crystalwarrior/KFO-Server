import asyncio
import time

"""
Module that contains the StepTimerManager class, which itself contains the StepTimer class.

A step timer is a timer with an apparent timer value that ticks up/down a fixed period of time once
every fixed interval (a step). This allows timers that simulate slow downs or fast forwarding (for
example, a timer that ticks down one second once every real 5 seconds).
A step timer when initialized does not start automatically, but once it starts, it can be paused
(where the apparent timer will not change) and unpaused (where the apparent timer will change by
the interval rules). The length of the first step after unpausing is set to be the current fixed
interval length minus the elapsed time in that step.
Once the apparent timer ticks below 0 or above _MAXIMUM_TIMER_VALUE, it will end automatically
and be deleted.
A step timer can also be canceled before it automatically ends.

A step timer allows the implementation different callback functions that will be executed on the
following events:
* When the step timer starts.
* When the step timer ticks up/down once the interval elapses.
* When the step timer is paused.
* When the step timer is unpaused.
* When the step timer ends automatically by going below 0.
* When the step timer ends automatically by going above _MAXIMUM_TIMER_VALUE
* When the step timer is canceled.
"""

class StepTimerManager:
    class StepTimer:
        async def _no_action():
            await asyncio.sleep(0)

        _DEF_TIMESTEP_LENGTH = 16/1000 # Length of one frame assuming 60 FPS

        def __init__(self, server, manager, loop, timer_id, timer_value,
                     timestep_length=_DEF_TIMESTEP_LENGTH, firing_interval=None,
                     cb_start_args=tuple(), cb_firing_args=tuple(),
                     cb_pause_args=tuple(), cb_resume_args=tuple(),
                     cb_end_min_args=tuple(), cb_end_max_args=tuple(),
                     cb_cancel_args=tuple()):

            if firing_interval is None:
                firing_interval = abs(timestep_length)

            self._server = server
            self._manager = manager
            self._loop = loop
            self._timer_id = timer_id
            self._timer_value = timer_value

            self._timestep_length = timestep_length/1000
            self._firing_interval = firing_interval/1000
            self._cb_start_args = cb_start_args
            self._cb_firing_args = cb_firing_args
            self._cb_pause_args = cb_pause_args
            self._cb_resume_args = cb_resume_args
            self._cb_end_min_args = cb_end_min_args
            self._cb_end_max_args = cb_end_max_args
            self._cb_cancel_args = cb_cancel_args

            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False
            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0

            self._MAXIMUM_TIMER_VALUE = 60*60*6 # 6 hours
            self._task = None
            self._manager._timers[self._timer_id] = self._task

        def start(self):
            async_function = self.as_timer()
            self._task = asyncio.ensure_future(async_function, loop=self._loop)

        def pause(self):
            self._just_paused = True
            self.cancel()

        def resume(self):
            self._is_paused = False
            self._just_unpaused = True

        def cancel(self):
            self._task.cancel()
            asyncio.ensure_future(self.await_cancellation(self._task))

        async def await_cancellation(self, old_task):
            # Wait until it is able to properly retrieve the cancellation exception
            try:
                await old_task
            except asyncio.CancelledError:
                pass

        async def _cb_start_fn(self, *args):
            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0
            self._is_paused = False
            self._just_paused = False
            self._just_unpaused = False

        async def _cb_firing_fn(self, *args):
            self._last_timestep_time = time.time()
            self._subtimestep_elapsed = 0
            await asyncio.sleep(self._firing_interval)

        async def _cb_pause_fn(self, *args):
            self._subtimestep_elapsed += time.time() - self._last_timestep_time
            await asyncio.sleep(self._firing_interval)

        async def _cb_resume_fn(self, *args):
            adapted_firing_interval = max(0, self._firing_interval - self._subtimestep_elapsed)
            await asyncio.sleep(adapted_firing_interval)

        async def _cb_end_min_fn(self, *args):
            pass

        async def _cb_end_max_fn(self, *args):
            pass

        async def _cb_cancel_fn(self, *args):
            pass

        async def as_timer(self):
            self._cb_start_fn(*self._cb_start_args)

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
                        await self._cb_resume_fn(*self._cb_resume_args)
                    # Otherwise, timer is paused, wait timestep miliseconds again
                    else:
                        await asyncio.asleep(self._timestep_length)
                except asyncio.CancelledError:
                    # Code can run here for one of two reasons
                    # 1. The timer was canceled
                    # 2. The timer was just paused
                    if not self._is_paused:
                        await self._cb_cancel_fn(*self._cb_cancel_args)
                        break
                    else:
                        self._just_paused = True
                        await self._cb_pause_fn(*self._cb_pause_args)
                else:
                    if (not self._is_paused and not self._just_unpaused):
                        self._timer_value += self._timestep_length

                        # Check if timer has gone beyond limits, and if so automatically end it
                        if self._timer_value <= 0:
                            self._cb_end_min_fn(*self._cb_end_min_args)
                            break
                        elif self._timer_value > self._MAXIMUM_TIMER_VALUE:
                            self._cb_end_max_fn(*self._cb_end_max_args)
                            break
