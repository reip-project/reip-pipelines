import glob
import time
import fnmatch
import itertools
import collections
import numpy as np

import reip
from reip.util import text


class Iterator(reip.Block):
    '''Yield each element in an iterator one at a time.'''
    def __init__(self, iterator, **kw):
        self.iterator = iter(iterator)
        super().__init__(n_inputs=0, **kw)

    def process(self, meta=None):
        try:
            x = next(self.iterator)
            return [x], {}
        except StopIteration:
            return reip.CLOSE


class Interval(reip.Block):
    '''Emit every X seconds.'''
    def __init__(self, seconds=2, initial=None, **kw):
        self.seconds = seconds
        self.initial = initial
        super().__init__(n_inputs=0, max_rate=1/seconds, **kw)

    def init(self):
        time.sleep(self.initial or 0)

    def process(self, meta=None):
        return [None], {'time': time.time()}


# class ControlledDelay(reip.Block):
#     '''Add system time to metadata.'''
#     def process(self, x, meta=None):
#         time.sleep(x)
#         return [None], {'time': time.time()}


class Time(reip.Block):
    '''Add system time to metadata.'''
    def __init__(self, **kw):
        super().__init__(**kw)

    def process(self, x, meta):
        return [x], {'time': time.time()}


class Meta(reip.Block):
    '''Add arbitrary data to metadata.'''
    def __init__(self, meta, **kw):
        self.meta = meta or {}
        super().__init__(*a, **kw)
    def process(self, x, meta=None):
        return [x], {
            k: v(meta) if callable(v) else v
            for k, v in self.meta.items()
        }



class Glob(reip.Block):
    '''Outputs files matching glob patterns.'''
    def __init__(self, *paths, recursive=True, atonce=False, **kw):
        self.paths = paths
        self.recursive = recursive
        self.atonce = atonce  # return all files at once
        super().__init__(n_inputs=0, **kw)

    def init(self):
        self.last = set()

    def process(self, meta=None):
        fs = {f for p in self.paths for f in glob.glob(p, recursive=self.recursive)}
        self.last, fs = fs, fs - self.last
        if self.atonce:
            yield [fs], {}
        else:
            for f in fs:
                yield [f], {}

# as an experiment:
# @reip.helpers.asbasiccontext
# def Glob(self, *paths, atonce=False):
#     self.last = set()
#     def process():
#         fs = {f for p in paths for f in glob.glob(p)}
#         self.last, fs = fs, fs - self.last
#         if atonce:
#             yield fs
#         else:
#             yield from fs
#     yield process


# class Dict(reip.Block):
#     '''Merge block outputs into a dict.'''
#     def __init__(self, meta, *a, **kw):
#         super().__init__(*a, **kw)
#
#     def process(self, *xs, meta=None):
#         return [xs], {}

class AsDict(reip.Block):
    '''Merge block outputs into a dict.'''
    def __init__(self, *columns, prepare=lambda c, x: (c, x), meta=None, **kw):
        self.columns = columns
        self.prepare = prepare
        self.meta_keys = reip.util.as_list(meta or ())
        super().__init__(n_inputs=len(columns), **kw)

    def process(self, *xs, meta=None):
        data = {}
        # set data buffer keys
        for c, x in zip(self.columns, xs):
            c, x = self.prepare(c, x)
            if isinstance(c, (list, tuple, np.ndarray)):
                data.update(zip(c, reip.util.as_iterlike(x)))
            else:
                data[c] = x
        # set meta keys
        if self.meta_keys:
            data.update({
                k: meta[k] for k in meta
                if any(fnmatch.fnmatch(k, p) for p in self.meta_keys)
            })
        return [data], {}


# class Sleep(reip.Block):
#     def __init__(self, sleep=2, **kw):
#         self.sleep = sleep
#         super().__init__(**kw)

#     def process(self, x, meta):
#         time.sleep(self.sleep)
#         return [x], meta


class Constant(reip.Block):
    '''Yields a constant value.'''
    def __init__(self, value, *a, **kw):
        self.value = value
        super().__init__(*a, n_inputs=0, **kw)

    def process(self, meta):
        return [self.value], meta


class Increment(Iterator):
    '''Yield an incrementing (or decrementing) value.'''
    def __init__(self, start=None, stop=None, step=1, **kw):
        if stop is None:
            start, stop = 0, start
        super().__init__(
            range(start or 0, stop, step) if stop is not None else
            itertools.count(start or 0, step or 1), **kw)


class Debug(reip.Block):
    '''Debug the output of a block.'''
    level = 'debug'
    log_level = 'debug'
    def __init__(self, message=None, level=None, convert=None, value=False, compact=False,
                 summary=False, period=None, name=None, border=False, log_level=None, **kw):
        self.message = message or 'Debug'
        self.value = value
        self.period = period
        self._summary = summary
        self._border = border
        self._last_time = 0
        self.level = reip.util.logging.aslevel(level or self.level)
        self.convert = convert
        self.compact = compact
        name = 'Debug-{}'.format(message.replace(" ", "-")) if message else None
        super().__init__(name=name, log_level=log_level or self.log_level, **kw)

    def _block_line_format(self, x):
        if self.convert:
            return type(x).__name__, self.convert(x)
        if isinstance(x, np.ndarray):
            if self._summary:
                return x.shape, x.dtype, 'min:', x.min(), 'max:', x.max(), 'mean:', x.mean()
            if x.size > 40 or x.ndim > 2:
                return x.shape, x.dtype, x if self.value else '' # , f'{np.isnan(x).sum()} nans'
            return x.shape, x.dtype, x
        return type(x).__name__, x

    def _block_format(self, *xs, meta):
        data = [self._block_line_format(x) for x in xs]

        return (text.block_text if self._border else text.b_)(
            text.blue(self.message),
            *(
                (('data:', data, '||', 'meta:', meta),)
                if self.compact else
                ('data:', *[('  ',i)+tuple(d) for i,d in enumerate(data)], ('meta:', meta))
            )
        )

    def process(self, *xs, meta=None):
        if not self.period or time.time() - self._last_time > self.period:
            self._last_time = time.time()
            self.log.log(self.level, self._block_format(*xs, meta=meta))
            # print(, flush=True)
        return xs, meta


class Results(reip.Block):
    '''Gather the results in lists as self.results and self.meta'''
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
    '''An inline way to create a block from a regular function. Input and output formats are the same.'''
    def __init__(self, func=None, name=None, init=None, finish=None, n_inputs=None, **kw):
        self.func = func or (lambda *a, **kw: None)
        self.init_func = init
        self.finish_func = finish
        if not func:  # don't run too fast if there's no process function
            kw.setdefault('max_rate', 1)
        super().__init__(
            name=name or self.func.__name__, 
            n_inputs=n_inputs, **kw)

    def init(self):
        if self.init_func:
            self.init_func()

    def process(self, *xs, meta=None):
        return self.func(*xs, meta=meta)

    def finish(self):
        if self.finish_func:
            self.finish_func()

    @classmethod
    def define(cls, func):
        return cls(func)


class Interleave(reip.Block):
    '''Interleave the block inputs to a single output.'''
    def __init__(self, sort_key=None, **kw):
        super().__init__(n_inputs=None, **kw)
        self.sort_key = sort_key

    def process(self, *xs, meta=None):
        if self.sort_key:
            xs = [x for i, x in sorted(enumerate(xs), key=lambda x: meta[x[0]][self.sort_key])]
        for x in xs:
            if x is not None:
                yield [x], meta


class Separate(reip.Block):
    '''Separate out a single input into multiple outputs based on a condition per output.
    '''
    def __init__(self, bins, **kw):
        self.bins = bins
        super().__init__(n_outputs=len(bins), **kw)

    def process(self, x, meta=None):
        out = [None]*len(self.bins)
        for i, check in enumerate(self.bins):
            if check(x, meta):
                out[i] = x
                break
        return out, meta


class Gather(reip.Block):
    def __init__(self, size=None, reduce=None, squeeze=True, **kw):
        self.size = size
        self.reduce = reduce
        self.squeeze = squeeze
        super().__init__(**kw)

    def init(self):
        self.items = []

    def _should_fire(self):
        return len(self.items) >= self.size

    def process(self, *xs, meta=None):
        if self.squeeze and len(xs) == 1:
            xs = xs[0]
        self.items.append(xs)
        if self._should_fire():
            items, self.items = self.items, []
            if self.reduce:
                items = self.reduce(items)
            return [items], meta

    def finish(self):
        self.items = None
