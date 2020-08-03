import time
import itertools
import numpy as np


def loop():
    while True:
        yield

def timed(it, duration=None):
    if not duration:
        yield from it
        return

    t0 = time.time()
    for x in it:
        yield x
        if time.time() - t0 >= duration:
            return


def throttled(it, rate=None, delay=1e-6):
    if not rate:
        yield from it
        return

    t1 = time.time()
    for x in it:
        yield x
        t1, t0 = time.time(), t1
        dt = (1. / rate) - (t1 - t0 + 0.5 * delay)
        if dt:  # where's my walrus op ?
            time.sleep(dt)


def peakiter(it, n=1):
    '''Check the value first n items of an iterator without unloading them from
    the iterator queue.'''
    it = iter(it)
    items = [_ for _, i in zip(it, range(n))]
    return items, itertools.chain(items, it)


# numpy

def npgenarray(it, shape, **kw):
    '''Create a np.ndarray from a generator. Must specify at least the length
    of the generator or the entire shape of the final array.'''
    if isinstance(shape, int):
        (x0,), it = peakiter(it)
        shape = (shape,) + x0.shape
    X = np.zeros(shape, **kw)
    for i, x in enumerate(it):
        X[i] = x
    return X


def npmaparray(func, X):
    return npgenarray((func(x) for x in X), len(X))
