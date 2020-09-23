import time
import numpy as np
import reip


class SomeArray(reip.Block):
    exec_mode = 'process'
    def __init__(self, shape, **kw):
        self.shape = shape
        self.array = None
        super().__init__(n_source=0, **kw)

    def init(self):
        self.array = np.ones(self.shape, dtype=np.uint8)

    def process(self, meta):
        return [self.array], {'shape': self.shape}

    def finish(self):
        self.array = None


class SomeTransform(reip.Block):
    def __init__(self, offset=0, **kw):
        self.offset = offset
        super().__init__(n_source=None, **kw)

    def process(self, *data, meta=None):
        return data, {'offset': self.offset}


class TimeBomb(reip.Block):
    clock = None
    def __init__(self, t_minus=5, min_rate=0.001, **kw):
        self.t_minus = t_minus
        super().__init__(n_source=None, min_rate=min_rate, **kw)

    def init(self):
        self.clock = time.time()

    def process(self, *xs, meta):
        dt = self.t_minus - (time.time() - self.clock)
        if dt <= 0:
            raise TimeoutError('boom!')
        return [dt], {}


class TextFile(reip.Block):
    def __init__(self, content, fname=None, **kw):
        self.content = (
            content if callable(content) else str(content or '').format)
        self.fname = str(fname)
        super().__init__(n_source=None, **kw)

    def process(self, *xs, meta):
        fname = self.fname.format(*xs, **meta)
        with open(fname, 'w') as f:
            f.write(self.content(*xs, **meta))
        return [fname], {}
