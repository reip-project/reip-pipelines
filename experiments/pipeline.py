import time
import queue
import multiprocessing as mp
from interface import Source
from ring_buffer import RingBuffer
from dummies import *
from task import *
import pyarrow as pa
import numpy as np
import pyarrow.plasma as plasma
client = plasma.connect("/tmp/plasma")

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

class Test:
    def __init__(self, value):
        self.var = mp.Value('i', value, lock=False)
        print("init", self.var.value)

    def change(self, add):
        self.var.value += add

    def run(self, arg):
        print("run", self.var.value)
        time.sleep(0.5)
        self.change(arg)
        print("run2", self.var.value)


if __name__ == '__main__':
    t = Test(10)
    print("main", t.var.value)

    p = mp.Process(target=t.run, args=(10,))
    p.start()
    time.sleep(0.25)

    t.change(5)
    print("main2", t.var.value)

    p.join()
    print("main3", t.var.value)

    n = np.ones((10, 2))
    # n.flags.writeable = False
    print(n)
    a = pa.Tensor.from_numpy(n)
    print(a)
    # a[1, :] = 0
    n2 = a.to_numpy()
    print(n2)
    n[5, :] = 0
    print(n2)

    d = {"hi": 0, "bye": 1}


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
