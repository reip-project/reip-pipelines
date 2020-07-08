import time
import queue
import numpy as np
from block import Block
from ring_buffer import RingBuffer


class Generator(Block):
    def __init__(self, name, shape, **kw):
        self.shape = shape
        self.array = None
        super().__init__(name, Block.SINK, **kw)
        # self._process_delay = None
        # self._process_delay = 1e-6

    def initialize(self):
        self.array = np.ones(self.shape, dtype=np.uint8)

    # def start(self):
    #     super().start()

    def process(self, data, meta):
        return self.array, {"shape": self.shape}
        # return self.array * self._processed, {"shape": self.shape}

    # def stop(self):
    #     super().stop()

    def finish(self):
        self.array = None

    # def __enter__(self):
    #     self.start()
    #     return self
    #
    # def __exit__(self, type, value, traceback):
    #     self.stop()
    #     return False


class Transformer(Block):
    def __init__(self, name, offset, **kw):
        self.offset = offset
        super().__init__(name, Block.SOURCE | Block.SINK, **kw)
        # self._process_delay = None
        # self._process_delay = 1e-6

    def initialize(self):
        pass

    def process(self, data, meta):
        meta = dict(meta)
        meta["offset"] = self.offset
        return data, meta
        # return data + self.offset, meta

    def finish(self):
        pass


class Consumer(Block):
    def __init__(self, name, prefix, **kw):
        self.prefix = prefix
        super().__init__(name, Block.SOURCE | Block.SINK, **kw)
        # self._process_delay = None
        # self._process_delay = 1e-6

    def initialize(self):
        pass

    def process(self, data, meta):
        meta = dict(meta)
        meta["prefix"] = self.prefix
        return self.prefix + str(self._processed), meta

    def finish(self):
        pass


if __name__ == '__main__':
    gen = Generator("data_gen", (720, 1280, 3), sink=RingBuffer(1000))
    # gen = Generator("data_gen", (720, 1280, 3), sink=queue.Queue())
    # gen = Generator("data_gen", (720, 1280, 3), sink=queue.Queue(maxsize=100000))

    gen.spawn()
    # while not gen.ready:
    #     time.sleep(1e-3)

    gen.start()
    time.sleep(0.1)

    # gen.terminate = True
    gen.join()

    gen.print_stats()

    # print("Generated", gen._generated, "buffers")

    # while not gen.sink.empty():
    #     print(gen.sink.get())
