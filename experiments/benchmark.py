from dummies import *
from task import *
import pyarrow.plasma as plasma


if __name__ == '__main__':
    client = plasma.connect("/tmp/plasma")
    print(client.store_capacity())
    print(client.list())
    client.delete(client.list())
    print(client.list())

    with Graph("pipeline") as p:
        with Task("camera") as t:
            # Generator("cam", (1, 128, 1), max_rate=None, verbose=True)
            # Generator("cam", (1, 1280, 3), max_rate=None, verbose=True)
            Generator("cam", (2592 * 1944 * 3 // 2), max_rate=None, verbose=True)
            # Generator("cam", (720, 1280, 3), max_rate=None, verbose=True)
            t.cam.to(Transformer("inf", offset=1, verbose=False))
        Consumer("f", prefix="test", verbose=True)
        t.inf.to(p.f, plasma=True, faster_queue=True)
        p.f.sink = queue.Queue()

    p.run(1)

    files = []
    while not p.f.sink.empty():
        files.append(p.f.sink.get()[0])
    print(len(files), files)
