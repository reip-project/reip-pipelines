import time
import itertools
import numpy as np

import reip
from reip.util import text


class Iterator(reip.Block):
    '''Call this function every X seconds'''
    def __init__(self, iterator, **kw):
        self.iterator = iter(iterator)
        super().__init__(n_source=0, **kw)

    def process(self, meta=None):
        try:
            x = next(self.iterator)
            return [x], {}
        except StopIteration:
            return reip.CLOSE


class Interval(reip.Block):
    '''Call this function every X seconds'''
    def __init__(self, seconds=2, **kw):
        self.seconds = seconds
        super().__init__(n_source=0, **kw)

    def process(self, meta=None):
        time.sleep(self.seconds)
        return [None], {'time': time.time()}


class Time(reip.Block):
    '''Add system time to metadata.'''
    def process(self, x, meta=None):
        return [x], {'time': time.time()}


class Meta(reip.Block):
    '''Add arbitrary data to metadata.'''
    def __init__(self, meta, *a, **kw):
        self.meta = meta or {}
        super().__init__(*a, **kw)
    def process(self, x, meta=None):
        return [x], {
            k: v(meta) if callable(v) else v
            for k, v in self.meta.items()
        }


class Dict(reip.Block):
    '''Merge block outputs into a dict.'''
    def __init__(self, meta, *a, **kw):
        super().__init__(*a, **kw)

    def process(self, *xs, meta=None):
        return [xs], {}


class Sleep(reip.Block):
    def __init__(self, sleep=2, **kw):
        self.sleep = sleep
        super().__init__(**kw)

    def process(self, x, meta):
        time.sleep(self.sleep)
        return [x], meta


class Constant(reip.Block):
    def __init__(self, value, *a, **kw):
        self.value = value
        super().__init__(*a, n_source=0, **kw)

    def process(self, meta):
        return [self.value], meta


class Increment(Iterator):
    def __init__(self, start=None, stop=None, step=1, **kw):
        if stop is None:
            start, stop = 0, start
        super().__init__(
            range(start or 0, stop, step) if stop is not None else
            itertools.count(start or 0, stop), **kw)


class Debug(reip.Block):
    def __init__(self, message=None, value=False, summary=False, period=None, name=None, **kw):
        self.message = message or 'Debug'
        self.value = value
        self.period = period
        self._summary = summary
        self._last_time = 0
        name = 'Debug-{}'.format(message.replace(" ", "-")) if message else None
        super().__init__(name=name, **kw)

    def _format(self, x):
        if isinstance(x, np.ndarray):
            if self._summary:
                return x.shape, x.dtype, 'min:', x.min(), 'max:', x.max(), 'mean:', x.mean()
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


class Results(reip.Block):
    squeeze = True
    def __init__(self, squeeze=True, **kw):
        self.squeeze = squeeze
        super().__init__(**kw)

    def init(self):
        self.results = []
        self.meta = []

    def process(self, *xs, meta=None):
        self.results.append(xs[0] if self.squeeze and len(xs) == 1 else xs)
        self.meta.append(meta)


class Lambda(reip.Block):
    def __init__(self, func, name=None, **kw):
        self.func = func
        name = name or self.func.__name__
        if name == '<lambda>':
            name = '_lambda_'  # how to get the signature?
        super().__init__(name=name, **kw)

    def process(self, *xs, meta=None):
        return self.func(*xs, meta=meta)

    @classmethod
    def define(cls, func):
        return cls(func)
