import time
import queue
import multiprocessing as mp
from interface import Source
from ring_buffer import RingBuffer
from dummies import *
from task import *
from util import *
import pyarrow as pa
import numpy as np
import pyarrow.plasma as plasma

# class TestTask(Task):
#     def __init__(self, name, **kw):
#         super().__init__(name, **kw)
#
#     def build(self):
#         gen = self.add(Generator("data_gen", (720, 1280, 3), max_rate=None))
#         trans = self.add(Transformer("data_trans", 10))
#         eat = self.add(Consumer("data_eat", "test"))
#
#         gen.sink = RingBuffer(1000)
#         trans.sink = RingBuffer(1000)
#         eat.sink = queue.Queue()
#
#         gen.child(trans, strategy=Source.Skip, skip=1).child(eat, strategy=Source.All)

# class Test:
#     def __init__(self, value):
#         self.var = mp.Value('i', value, lock=False)
#         print("init", self.var.value)
#
#     def change(self, add):
#         self.var.value += add
#
#     def run(self, arg):
#         print("run", self.var.value)
#         time.sleep(0.5)
#         self.change(arg)
#         print("run2", self.var.value)


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


class Camera(Task):
    def build(self, resolution=(1080, 1920, 3), fps=30):
        self.gen = Generator("cam", resolution, max_rate=fps)
        self.fmt = Transformer("conv", offset=1)
        self.gen.child(self.fmt)


class Microphone(Task):
    def build(self, sampling_rate=48000, channels=16):
        self.gen = Generator("mic", (sampling_rate // 200, channels), max_rate=200)
        self.fmt = Transformer("sync", offset=10)
        self.gen.child(self.fmt)


class Video(Task):
    def build(self, cam1, cam2, classes=10):
        self.inf = Inference("ssd", classes=classes)
        self.inf[0].parent(cam1.fmt, strategy=Source.Latest)
        self.inf[1].parent(cam2.fmt, strategy=Source.Latest)


class Audio(Task):
    def build(self, mic, window=1024):
        self.spl = SPL("spl", window=window)
        self.spl.parent(mic.fmt)


class Writer(Task):
    def build(self, prefix="test", max_rate=50):
        self.f = Consumer("f", prefix=prefix, max_rate=max_rate)
        self.f.sink = mp.Queue()


if __name__ == '__main__':
    client = plasma.connect("/tmp/plasma")
    print(client.store_capacity())
    print(client.list())
    client.delete(client.list())
    print(client.list())

    # cam = Camera("Camera", resolution=(720, 1280, 3), fps=None)
    # f = Writer("File", prefix="vid", max_rate=None)
    # f.f.parent(cam.fmt, strategy=Source.Skip, skip=0)
    # all = [cam, f]

    cam1 = Camera("wide")
    cam2 = Camera("zoom", resolution=(720, 1280, 3), fps=240)
    mic = Microphone("array")

    vid = Video("vid", cam1, cam2)
    aud = Audio("aud", mic)

    f_vid = Writer("f_vid", prefix="video")
    f_aud = Writer("f_aud", prefix="audio")

    vid.inf[0].child(f_vid.f, strategy=Source.Skip, skip=0)
    aud.spl.child(f_aud.f, strategy=Source.Skip, skip=0)

    all = [cam1, cam2, mic, vid, aud, f_vid, f_aud]

    for t in all:
        t.start()

    for t in all:
        while not t.ready.value:
            time.sleep(1e-6)

    for t in all:
        t.remote(t.resume)

    time.sleep(1)

    for t in all:
        t.remote(t.pause)

    for t in all:
        t.join()

    # files = []
    # while not f.f.sink.empty():
    #     files.append(f.f.sink.get()[0])
    #
    # print(files)

    vid_files = []
    aud_files = []

    while not f_vid.f.sink.empty():
        vid_files.append(f_vid.f.sink.get()[0])

    while not f_aud.f.sink.empty():
        aud_files.append(f_aud.f.sink.get()[0])

    print(vid_files)
    print(aud_files)

    # t = Timer()


    # t = Test(10)
    # print("main", t.var.value)
    #
    # p = mp.Process(target=t.run, args=(10,))
    # p.start()
    # time.sleep(0.25)
    #
    # t.change(5)
    # print("main2", t.var.value)
    #
    # p.join()
    # print("main3", t.var.value)
    #
    # n = np.ones((10, 2))
    # # n.flags.writeable = False
    # print(n)
    # a = pa.Tensor.from_numpy(n)
    # print(a)
    # # a[1, :] = 0
    # n2 = a.to_numpy()
    # print(n2)
    # n[5, :] = 0
    # print(n2)
    #
    # d = {"hi": 0, "bye": 1}


    # task = TestTask("test")
    #
    # task.spawn()
    #
    # with task:
    #     time.sleep(0.1)
    #
    # task.join()
    # task.print_stats()
    #
    # files = []
    # while not task["data_eat"].sink.empty():
    #     files.append(task["data_eat"].sink.get()[0])
    # print(len(files), "files", files)
