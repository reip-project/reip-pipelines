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


def test1(client):
    with Graph() as p:
        Generator("cam", (720, 1280, 3), max_rate=None)
        Transformer("inf", offset=1)
        Consumer("f", prefix="test")
        p.cam.to(p.inf).to(p.f)
        # p.cam.to(p.f)
        p["f"].sink = queue.Queue()

    p.spawn_all()

    p.start_all()
    time.sleep(0.1)
    p.stop_all()

    p.join_all()

    print()
    p.print_stats()

    files = []
    while not p.f.sink.empty():
        files.append(p.f.sink.get()[0])
    print(len(files), files)


def test2(client):
    with Graph("pipeline") as p:
        with Task("camera") as t:
            # Generator("cam", (1, 1280, 3), max_rate=None)
            # Generator("cam", (2000, 2500, 3), max_rate=None)
            Generator("cam", (720, 1280, 30), max_rate=None)
            t.cam.to(Transformer("inf", offset=1))
        Consumer("f", prefix="test")
        t.inf.to(p.f)
        p.f.sink = queue.Queue()

    p.spawn_all()

    p.start_all()
    time.sleep(1)
    p.stop_all()

    p.terminate_all()
    print()
    print(p)
    # p.print_stats()

    p.join_all()

    files = []
    while not p.f.sink.empty():
        files.append(p.f.sink.get()[0])
    print(len(files), files)


if __name__ == '__main__':
    client = plasma.connect("/tmp/plasma")
    print(client.store_capacity())
    print(client.list())
    client.delete(client.list())
    print(client.list())

    test2(client)
    exit(0)

    # cam = Camera("Camera", resolution=(1, 1, 3), fps=None)
    cam = Camera("Camera", resolution=(720, 1280, 3), fps=None)
    f = Writer("File", prefix="vid", max_rate=None)
    f.f.parent(cam.fmt, strategy=Source.Skip, skip=0)
    all = [cam, f]

    # cam1 = Camera("wide")
    # cam2 = Camera("zoom", resolution=(720, 1280, 3), fps=240)
    # mic = Microphone("array")
    #
    # vid = Video("vid", cam1, cam2)
    # aud = Audio("aud", mic)
    #
    # f_vid = Writer("f_vid", prefix="video")
    # f_aud = Writer("f_aud", prefix="audio")
    #
    # vid.inf[0].child(f_vid.f, strategy=Source.Skip, skip=0)
    # aud.spl.child(f_aud.f, strategy=Source.Skip, skip=0)
    #
    # all = [cam1, cam2, mic, vid, aud, f_vid, f_aud]

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

    files = []
    while not f.f.sink.empty():
        files.append(f.f.sink.get()[0])

    print(files)

    # vid_files = []
    # aud_files = []
    #
    # while not f_vid.f.sink.empty():
    #     vid_files.append(f_vid.f.sink.get()[0])
    #
    # while not f_aud.f.sink.empty():
    #     aud_files.append(f_aud.f.sink.get()[0])
    #
    # print(vid_files)
    # print(aud_files)

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
