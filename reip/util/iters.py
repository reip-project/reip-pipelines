import time
import itertools
import numpy as np


def loop():
    '''Infinite loop'''
    while True:
        yield

def timed(it, duration=None):
    '''Run a loop for a predetermined amount of time.'''
    if not duration:
        yield from it
        return

    t0 = time.time()
    for x in it:
        if time.time() - t0 >= duration:
            break
        yield x


def throttled(it, rate=None, delay=1e-6):
    '''Throttle a loop to take '''
    if not rate:
        yield from it
        return

    t1 = time.time()
    for x in it:
        yield x
        t1, t0 = time.time(), t1
        dt = max((1. / rate) - (t1 - t0 + 0.5 * delay), 0)
        if dt:
            time.sleep(dt)
        # wraps around for _ in because that may take a non-trivial amount of time
        # e.g. (time.sleep(1) for _ in loop())
        t1 = time.time()


def resample_iter(it, interval):
    if not interval:
        yield from it
        return

    t = time.time()
    for _ in it:
        if time.time() - t >= interval:
            t = time.time()
            yield _


def limit(it, n=None):
    if not n:
        yield from it
        return
    # yield only n elements
    for i, x in zip(range(n), it):
        yield x


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
    X = np.empty(shape, **kw)
    for i, x in enumerate(it):
        X[i] = x
    return X


def npmaparray(func, X):
    return npgenarray((func(x) for x in X), len(X))


# if __name__ == '__main__':
# for _ in timed(throttled(loop(), 1), 10):
#     ...
