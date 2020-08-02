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
        super().__init__(**kw)

    def process(self, *data, meta=None):
        return data, {'offset': self.offset}
