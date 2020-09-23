import time
import functools



def throttle(func, duration=None):
    '''Don't call a function more frequently than `duration`. Caches the
    return value from the previous call.'''
    if not duration:
        return func

    @functools.wraps(func)
    def inner(*a, **kw):
        t = time.time()
        if t - inner.t0 >= duration:
            inner.t0 = t
            inner.retval = func(*a, **kw)
        return inner.retval

    inner.t0, inner.retval = 0, None
    return inner


def retry(func, n=5, exc=Exception):
    '''retry a function on failure.'''
    if not n or not exc:
        return func

    @functools.wraps(func)
    def inner(*a, **kw):
        for i in range(n):
            try:
                return func(*a, **kw)
            except exc:
                if i == n - 1:
                    raise

    return inner
