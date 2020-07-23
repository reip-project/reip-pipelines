import time
import queue
import numpy as np
from .block import Block
from .ring_buffer import RingBuffer


# class Generator2(Block):
#     def __init__(self, name, shape, **kw):
#         self.shape = shape
#         self.array = None
#         super().__init__(name, num_sinks=1, **kw)
#
#     def run(self):
#         array = np.ones(self.shape, dtype=np.uint8)
#         while True:
#             yield self.array, {"shape": self.shape}


class Generator(Block):
    def __init__(self, shape, **kw):
        self.shape = shape
        self.array = None
        super().__init__(num_sinks=1, **kw)
        print(666, shape)

    def init(self):
        self.array = np.ones(self.shape, dtype=np.uint8)

    def process(self, buffers):
        return [(self.array, {"shape": self.shape})]
        # return [(self.array * self.processed, {"shape": self.shape})]

    def finish(self):
        self.array = None


class Transformer(Block):
    def __init__(self, offset, **kw):
        self.offset = offset
        super().__init__(num_sources=1, num_sinks=1, **kw)

    def process(self, buffers):
        data, meta = buffers[0]
        return [(data + self.offset, dict(meta, offset=self.offset))]


class Consumer(Block):
    def __init__(self, prefix, **kw):
        self.prefix = prefix
        super().__init__(num_sources=1, num_sinks=1, **kw)

    def process(self, buffers):
        data, meta = buffers[0]
        return [(self.prefix + str(self.processed), dict(meta, prefix=self.prefix))]


if __name__ == '__main__':
    gen = Generator((720, 1280, 3), max_rate=500).queue(1000)

    gen.spawn()
    with gen:
        time.sleep(0.1)
    gen.join()
    gen.print_stats()
