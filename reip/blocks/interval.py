import time
import sched
from .block import Block

class _IgnoreScheduler(Exception): # dummy exception - no one would throw this
    '''Default ignored exception. Something no one would actually throw.'''

class Interval(Block):
    name = 'interval'
    def __init__(self, interval=1, ignore=None, priority=0, initial_delay=0):
        self.interval = interval
        self.initial_delay = interval if initial_delay is None else initial_delay
        sc = sched.scheduler(time.time, time.sleep)

        self.schedule = lambda *a, __interval=self.interval, **kw: sc.enter(
            __interval, priority, emit, a, kw)

        ignore = ignore or _IgnoreScheduler
        def emit(*a, **kw):
            try: # try to run the function
                self.run(*a, **kw)
            except ignore: # custom ignore exceptions
                pass
            self.schedule(*a, **kw)

    def __call__(self, **kw):
        self.schedule(**kw, __interval=self.initial_delay)
