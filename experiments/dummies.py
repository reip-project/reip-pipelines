import time
import queue
import numpy as np
from block import *
from ring_buffer import RingBuffer


class Generator(Block):
    def __init__(self, name, shape, **kw):
        self.shape = shape
        self.array = None
        super().__init__(name, num_sinks=1, **kw)

    def init(self):
        self.array = np.ones(self.shape, dtype=np.uint8)

    def process(self, buffers):
        return [(self.array, {"shape": self.shape})]
        # return [(self.array * self.processed, {"shape": self.shape})]

    def finish(self):
        self.array = None


class Transformer(Block):
    def __init__(self, name, offset, **kw):
        self.offset = offset
        super().__init__(name, num_sources=1, num_sinks=1, **kw)

    def process(self, buffers):
        data, meta = buffers[0]
        meta = dict(meta)
        meta["offset"] = self.offset
        return [(data, meta)]
        # return [(data + self.offset, meta)]


class Consumer(Block):
    def __init__(self, name, prefix, **kw):
        self.prefix = prefix
        super().__init__(name, num_sources=1, num_sinks=1, **kw)

    def process(self, buffers):
        data, meta = buffers[0]
        meta = dict(meta)
        # self.timestamp(meta)
        meta["prefix"] = self.prefix
        # return [(self.prefix + str(data.ravel()[0]), meta)]
        return [(self.prefix + str(self.processed), meta)]


if __name__ == '__main__':
    gen = Generator("data_gen", (720, 1280, 3), max_rate=500)
    # gen.sink = queue.Queue()
    gen[0].sink = RingBuffer(1000)

    gen.spawn()

    with gen:
        time.sleep(0.1)

    # gen.start()
    # time.sleep(0.1)

    gen.join()

    gen.print_stats()
