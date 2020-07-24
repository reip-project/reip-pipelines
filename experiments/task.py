from abc import ABC, abstractmethod
from interface import *
from block import *
from dummies import *
import multiprocessing as mp
from ctypes import c_bool
import traceback
import queue
import time


class Task(ABC):
    def __init__(self, name):
        self.name = name

        self.ready = mp.Value(c_bool, False)
        self.running = mp.Value(c_bool, False)
        self.terminate = mp.Value(c_bool, False)
        self.error = mp.Value(c_bool, False)
        self.done = mp.Value(c_bool, False)

        self._block_factory = {}
        self._select = 0

        self._process = None
        self._pipes = None
        self._debug = True
        self._verbose = True
        self._t0 = 0
        self._r0 = 0
        self._spawn_time = 0
        self._running_time = 0
        self._join_time = 0
        self._total_time = 0

        b0 = time.time()
        self.build()
        self._build_time = time.time() - b0
        if self._verbose:
            print("Task %s Built in %.3f sec" % (self.name, self._build_time))

    # Construction

    @abstractmethod
    def build(self):
        raise NotImplementedError

    def add(self, block):
        if block.name in self._block_factory.keys():
            raise ValueError("Block %s already exists in task %s" % (block.name, self.name))
        else:
            self._block_factory[block.name] = block
            block.task = self
            return block

    def __getitem__(self, key):
        if type(key) is str:
            return self._block_factory[key]
        elif type(key) is int:
            if key < 0:
                raise ValueError("Invalid key value")
            else:
                self._select = key
                return self
        else:
            raise TypeError("Invalid key type")

    # Operation

    def start(self):
        if not self.ready.value:
            raise RuntimeError("Task %s not ready to start" % self.name)
        else:
            self.running.value = True
            for name, block in self._block_factory.items():
                block.start()
            self._r0 = time.time()
            print("Started Task %s" % self.name)

    def __enter__(self):
        self.start()
        return self

    def stop(self):
        if not self.running.value:
            raise RuntimeError("Task %s not running" % self.name)
        else:
            self.running.value = False
            for name, block in self._block_factory.items():
                block.stop()
            self._running_time = time.time() - self._r0
            print("Stopped Task %s" % self.name)

    def __exit__(self, type, value, traceback):
        self.stop()
        return False

    def spawn(self, wait=True):
        self._process = mp.Process(target=self._run, name=self.name)
        self._process.daemon = True
        if self._verbose:
            print("Spawning task %s..." % self.name)
        self.ready.value = False
        self.done.value = False
        self._pipes = mp.Pipe()
        self._process.start()

        if wait:
            while not self.ready.value:
                time.sleep(1e-6)

        return self._pipes[0]

    def _run(self):
        try:
            self._t0 = time.time()
            s0 = time.time()
            for name, block in self._block_factory.items():
                block.spawn(wait=False)
            for name, block in self._block_factory.items():
                while not block.ready:
                    time.sleep(1e-6)
            self._spawn_time = time.time() - s0

            if self._verbose:
                print("Task %s Spawned in %.3f sec" % (self.name, self._spawn_time))
            self.ready.value = True

            # self.start()
            while not self.terminate.value:
                if self._pipes[1].poll():
                    msg = self._pipes[1].recv()
                    if msg == "start":
                        self.start()
                    elif msg == "stop":
                        self.stop()
                    elif msg == "terminate":
                        self.terminate.value = True
                    else:
                        print("Unsupported message: %s" % msg)
                time.sleep(1e-6)
            # self.stop()

            j0 = time.time()
            for name, block in self._block_factory.items():
                block.terminate = True
            for name, block in self._block_factory.items():
                block.join()
            self._join_time = time.time() - j0

            self._total_time = time.time() - self._t0
            if self._verbose:
                print("Task %s Finished after %.3f sec" % (self.name, self._total_time))
            self.done.value = True
            self.print_stats()
        except Exception as e:
            self.error.value = True
            self.exception = e
            traceback.print_exc()
            raise e

    def join(self, auto_terminate=True):
        if self._process is None:
            return

        if auto_terminate:
            self.terminate.value = True

        print("Joining task %s..." % self.name)
        self._process.join(timeout=1)  # Non-flushed queues might cause it to hang
        if self._debug:
            print("Joined task", self.name)

    def print_stats(self):
        for name, block in self._block_factory.items():
            if name != "data_eat":
                block.print_stats()
        service_time = self._total_time - (self._spawn_time + self._running_time + self._join_time)
        print("Total time for task %s %.3f sec:\n\t%.3f - *Build\n\t%.3f - Spawn\n\t%.3f - Running\n\t%.3f - Join\n\t%.3f - Service" %
              (self.name,  self._total_time, self._build_time, self._spawn_time, self._running_time, self._join_time, service_time))

        for name, block in self._block_factory.items():
            print("Block %s processed %d buffers" % (block.name, block.processed))


class TestTask(Task):
    # def __init__(self, name, **kw):
    #     super().__init__(name, **kw)

    def build(self):
        gen = self.add(Generator("data_gen", (720, 1280, 3), max_rate=None))
        trans = self.add(Transformer("data_trans", 10))
        eat = self.add(Consumer("data_eat", "test"))

        # gen.sink = RingBuffer(1000)
        # trans.sink = RingBuffer(1000)
        # eat.sink = queue.Queue(maxsize=10000)
        eat.sink = mp.Queue(maxsize=10000)
        # eat.sink = self[2].producer
        # eat.source = self[2].client

        gen.child(trans, strategy=Source.Skip, skip=0).child(eat, strategy=Source.All)


if __name__ == '__main__':
    task = TestTask("test")

    files = []
    pipe = task.spawn()

    t0 = time.time()
    pipe.send("start")

    while time.time() - t0 <= 1:
        while not task["data_eat"].sink.empty():
            files.append(task["data_eat"].sink.get()[0])
        time.sleep(1e-6)

    pipe.send("stop")
    time.sleep(1e-3)
    pipe.send("terminate")
    # time.sleep(3)
    # with task:
    #     time.sleep(0.1)

    # task["data_eat"].sink.join()
    task.join(auto_terminate=False)
    # task.print_stats()

    while not task["data_eat"].sink.empty():
        files.append(task["data_eat"].sink.get()[0])
    print(len(files), "files", files)
