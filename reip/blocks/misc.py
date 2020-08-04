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
        return type(x), x if self.value else ''

    def process(self, *xs, meta=None):
        if not self.period or time.time() - self._last_time > self.period:
            self._last_time = time.time()
            print(text.block_text(
                text.blue(self.message),
                'buffers:', *[
                    ('\t', i) + tuple(self._format(x))
                    for i, x in enumerate(xs)],
                ('meta:', meta)
            ), flush=True)
        return xs, meta
