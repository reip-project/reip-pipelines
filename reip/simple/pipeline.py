import time
import queue
from .interface import Source
from .dummies import *
from .task import *


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
#

class TestTask(Task):
    def init(self):
        self.gen = Generator((720, 1280, 3), max_rate=None).queue(1000)
        self.trans = Transformer(10).queue(1000)
        self.eat = Consumer('test').queue()
        self.gen.child(self.trans, strategy=Source.Skip, skip=1).child(self.eat)

if __name__ == '__main__':
    task = TestTask()

    task.spawn()
    with task:
        time.sleep(0.1)
    task.join()
    task.print_stats()

    files = []
    while not task['eat'].sink.empty():
        files.append(task['eat'].sink.get()[0])
    print(len(files), "files", files)
