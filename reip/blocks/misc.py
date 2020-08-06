import time
import numpy as np

import reip
from reip.util import text


class Interval(reip.Block):
    '''Call this function every X seconds'''
    def __init__(self, seconds=2, **kw):
        self.seconds = seconds
        super().__init__(n_source=0, **kw)

    def process(self, meta=None):
        time.sleep(self.seconds)
        meta['time'] = time.time()
        return (), {'time': time.time()}


class Sleep(reip.Block):
    def __init__(self, sleep=2, **kw):
        self.sleep = sleep
        super().__init__(**kw)

    def process(self, *ys, meta):
        time.sleep(self.sleep)
        return ys, meta


class Constant(reip.Block):
    def __init__(self, value, **kw):
        self.value = value
        super().__init__(**kw)

    def process(self, meta):
        return [self.value], meta


class Debug(reip.Block):
    def __init__(self, message='Debug', value=False, period=None, **kw):
        self.message = message
        self.value = value
        self.period = period
        self._last_time = 0
        super().__init__(**kw)

    def _format(self, x):
        if isinstance(x, np.ndarray):
            if x.size > 40 or x.ndim > 2:
                return x.shape, x.dtype, x if self.value else '' # , f'{np.isnan(x).sum()} nans'
            return x.shape, x.dtype, x
        return type(x).__name__, x

    def process(self, *xs, meta=None):
        if not self.period or time.time() - self._last_time > self.period:
            self._last_time = time.time()
            print(text.block_text(
                text.blue(self.message),
                'data:', *[
                    ('\t', i) + tuple(self._format(x))
                    for i, x in enumerate(xs)],
                ('meta:', meta)
            ), flush=True)
        return xs, meta


class Lambda(reip.Block):
    def __init__(self, func, name=None, **kw):
        self.func = func
        name = name or self.func.__name__
        if name is '<lambda>':
            name = 'how to get the signature?'
        super().__init__(name=name, **kw)

    def process(self, *xs, meta=None):
        return self.func(*xs, meta=meta)

    @classmethod
    def define(cls, func):
        return cls(func)
