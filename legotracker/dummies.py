import reip
import numpy as np


class Generator(reip.Block):
    debug = False
    inc = False

    def __init__(self, size=(1,), dtype=np.int, **kw):
        self.size = size
        self.dtype = np.dtype(dtype)
        self.array_0, self.array_1 = None, None
        
        super().__init__(n_inputs=None, **kw)

    def init(self):
        self.array_0 = np.zeros(self.size, self.dtype)
        self.array_1 = np.ones(self.size, self.dtype)

    def process(self, *xs, meta=None):
        meta = {"size": self.size, "dtype": self.dtype.name, "i": self.processed}

        if self.debug:
            print("Generated:", meta)

        # if self.processed > 200:
        #     raise RuntimeError("Boom")
        #     # assert(2 == 5)

        if self.inc:
            return [self.array_1 * self.processed], meta
        else:
            return [self.array_0], meta

    def finish(self):
        self.array_0 = None
        self.array_1 = None


class BlackHole(reip.Block):
    debug = False

    def __init__(self, **kw):
        # self.debug = debug

        super().__init__(n_outputs=None, **kw)

    def process(self, xs, meta=None):
        if self.debug:
            print("Consumed:", xs, meta)

        return None


if __name__ == '__main__':
    Generator.debug = True

    g = Generator(size=(1000, 1000), dtype=np.float32)
    g.init()

    ret = g.process()
    print(ret)

    BlackHole.debug = True

    bh = BlackHole()
    print(bh)

    print(bh.process(ret[0][0], meta=ret[1]))
