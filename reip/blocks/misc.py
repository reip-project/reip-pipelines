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
    def __init__(self, message='Debug', value=True, **kw):
        self.message = message
        self.value = value
        super().__init__(**kw)

    def process(self, *xs, meta=None):
        print(text.block_text(
            text.blue(self.message),
            'buffers:',
            *[
                ('\t', i) + (
                    (x.shape, x.dtype, x if self.value else '')
                    if isinstance(x, np.ndarray) and (x.size > 40 or x.ndim > 2) else
                    (type(x), x if self.value else '')
                )
                for i, x in enumerate(xs)
            ],
            ('meta:', meta)
        ), flush=True)
        return xs, meta
