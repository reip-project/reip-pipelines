import time
import functools
from . import iters


def throttle(func, interval=None):
    '''Don't call a function more frequently than `duration`. Caches the
    return value from the previous call.'''
    if not interval:
        return func

    @functools.wraps(func)
    def inner(*a, **kw):
        t = time.time()
        if t - inner.t0 >= interval:
            inner.t0 = t
            inner.retval = func(*a, **kw)
        return inner.retval

    inner.t0, inner.retval = 0, None
    return inner


def retry(func, n=None, exc=Exception, log=None, **kw):
    '''retry a function on failure.'''
    @functools.wraps(func)
    def inner(*a, **kw):
        for i in iters.run_loop(n=n, **kw):
            try:
                return func(*a, **kw)
            except exc as e:
                if n is not None and i == n:
                    raise
                if log is not None:
                    log.error('({}, try={}) {}'.format(e.__class__.__name__, i+1, e))
    return inner
