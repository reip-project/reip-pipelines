# import time
# import queue
import numpy as np
from block import *
# from ring_buffer import RingBuffer


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


class Inference(Block):
    def __init__(self, name, classes, **kw):
        self.classes = classes
        super().__init__(name, num_sources=2, num_sinks=1, **kw)

    def process(self, buffers):
        data1, meta1 = buffers[0]
        data2, meta2 = buffers[1]
        meta = {"inference": self.classes, "cam1": dict(meta1), "cam2": dict(meta2)}
        data = np.zeros((1, self.classes, 2))
        data[:, :, 0] = data1[0, 0, 0]
        data[:, :, 1] = data2[0, 0, 0]
        time.sleep(0.05)
        # return [(data, meta)]
        return [(data, meta)]


class SPL(Block):
    def __init__(self, name, window, **kw):
        self.window = window
        super().__init__(name, num_sources=1, num_sinks=1, **kw)

    def process(self, buffers):
        data, meta = buffers[0]
        meta = dict(meta)
        data = np.ones(data.shape) * self.window
        return [(data, meta)]


# class Camera(Task):
#     def build(self, resolution=(1080, 1920, 3), fps=30):
#         self.gen = Generator("cam", resolution, max_rate=fps)
#         self.fmt = Transformer("conv", offset=1)
#         self.gen.child(self.fmt)
#
#
# class Microphone(Task):
#     def build(self, sampling_rate=48000, channels=16):
#         self.gen = Generator("mic", (sampling_rate // 200, channels), max_rate=200)
#         self.fmt = Transformer("sync", offset=10)
#         self.gen.child(self.fmt)
#
#
# class Video(Task):
#     def build(self, cam1, cam2, classes=10):
#         self.inf = Inference("ssd", classes=classes)
#         self.inf[0].parent(cam1.fmt, strategy=Source.Latest)
#         self.inf[1].parent(cam2.fmt, strategy=Source.Latest)
#
#
# class Audio(Task):
#     def build(self, mic, window=1024):
#         self.spl = SPL("spl", window=window)
#         self.spl.parent(mic.fmt)
#
#
# class Writer(Task):
#     def build(self, prefix="test", max_rate=50):
#         self.f = Consumer("f", prefix=prefix, max_rate=max_rate)
#         self.f.sink = mp.Queue()


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
