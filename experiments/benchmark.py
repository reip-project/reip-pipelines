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
            # Generator("cam", (1, 1280, 3), max_rate=None)
            # Generator("cam", (2000, 2500, 3), max_rate=None)
            Generator("cam", (720, 1280, 1), max_rate=None)
            t.cam.to(Transformer("inf", offset=1))
        Consumer("f", prefix="test")
        t.inf.to(p.f)
        p.f.sink = queue.Queue()

    p.run(0.1)

    files = []
    while not p.f.sink.empty():
        files.append(p.f.sink.get()[0])
    print(len(files), files)
