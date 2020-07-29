from abc import ABC, abstractmethod
from interface import *
from block import *
from dummies import *
import multiprocessing as mp
from ctypes import c_bool
import traceback
import queue
import time
import sys
import functools


class Task(mp.Process):
    _initialized = False

    def __init__(self, name, *args, **kwargs):
        mp.Process.__init__(self, target=self._run)
        # self.daemon = True  # Forces terminate() if parent process exits
        self._parent_pipe, self._child_pipe = mp.Pipe()
        self._exception = None
        self.name = name

        self.ready = mp.Value(c_bool, False)
        self.running = mp.Value(c_bool, False)
        self.terminate = mp.Value(c_bool, False)
        self.error = mp.Value(c_bool, False)
        self.done = mp.Value(c_bool, False)

        self._block_factory = {}
        self._select = 0
        self._value = 0

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
        self._initialized = True

        b0 = time.time()
        self.build(*args, **kwargs)
        self._build_time = time.time() - b0
        if self._verbose:
            print("Task %s Built in %.3f sec" % (self.name, self._build_time))

    @property
    def exception(self):
        if self._parent_pipe.poll():
            self._exception = self._parent_pipe.recv()
        return self._exception

    def run(self):
        try:
            mp.Process.run(self)
            self._child_pipe.send(None)
        except Exception as e:
            tb = traceback.format_exc()
            self._child_pipe.send((e, tb))
            # raise e  # You can still rise this exception if you need to

    # @staticmethod
    # def remote(func):
    #     @functools.wraps(func)
    #     def wrapper_remote(*args, **kwargs):
    #         return func(*args, **kwargs)
    #     return wrapper_remote

    class Decorators:
        @classmethod
        def remote(cls, func):
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                print("In wrapper of", self.name, func.__name__)
                self._parent_pipe.send((func.__name__, args, kwargs))
                return self._parent_pipe.recv()
                # return func(self, *args, **kwargs)
            return wrapper

    def remote(self, func, *args, **kwargs):
        self._parent_pipe.send((func.__name__, args, kwargs))
        # handle exception
        return self._parent_pipe.recv()

    # @Decorators.remote
    def resume(self):
        print("resume", self.name)
        self._start()

    # @Decorators.remote
    def pause(self):
        print("pause", self.name)
        self._stop()

    def count(self, value=None):
        print("count", self._value)
        self._value = (value or self._value) + 1
        return self._value

    # Construction

    # @abstractmethod
    def build(self, *args, **kwargs):
        raise NotImplementedError

    def add(self, block):
        if block.name in self._block_factory.keys():
            raise ValueError("Block %s already exists in task %s" % (block.name, self.name))
        else:
            self._block_factory[block.name] = block
            block.task = self
            # block.name = self.name + "." + block.name
            return block

    def __setattr__(self, name, value):
        # print("Inside", name)
        if self._initialized and issubclass(type(value), Block):
            print("Adding", name)
            self.add(value)
        super().__setattr__(name, value)

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

    def _start(self):
        if not self.ready.value:
            raise RuntimeError("Task %s not ready to start" % self.name)
        else:
            self.running.value = True
            for name, block in self._block_factory.items():
                block.start()
            self._r0 = time.time()
            print("Started Task %s" % self.name)

    def __enter__(self):
        self._start()
        return self

    def _stop(self):
        if not self.running.value:
            raise RuntimeError("Task %s not running" % self.name)
        else:
            self.running.value = False
            for name, block in self._block_factory.items():
                block.stop()
            self._running_time = time.time() - self._r0
            print("Stopped Task %s" % self.name)

    def __exit__(self, type, value, traceback):
        self._stop()
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

            # self._start()
            while not self.terminate.value:
                # if self._pipes[1].poll():
                #     msg = self._pipes[1].recv()
                if self._child_pipe.poll():
                    func, args, kwargs = self._child_pipe.recv()
                    # print(func, args, kwargs)
                    ret = getattr(self, func)(*args, **kwargs)
                    self._child_pipe.send(ret)
                # if self._child_pipe.poll():
                #     msg = self._child_pipe.recv()
                #     if msg == "start":
                #         self._start()
                #     elif msg == "stop":
                #         self._stop()
                #     elif msg == "terminate":
                #         self.terminate.value = True
                #     else:
                #         print("Unsupported message: %s" % msg)

                # Check for any exception returned by blocks
                time.sleep(1e-6)
            # self._stop()

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
            raise ValueError("Foo")
        except:
            self.error.value = True
            raise

    def join(self, auto_terminate=True):
        # if self._process is None:
        #     return

        if auto_terminate:
            self.terminate.value = True

        print("Joining task %s..." % self.name)
        # self._process.join(timeout=1)  # Non-flushed queues might cause it to hang
        super(mp.Process, self).join()
        if self._debug:
            print("Joined task", self.name)

    def print_stats(self):
        for name, block in self._block_factory.items():
            # if name != "data_eat":
            block.print_stats()
        service_time = self._total_time - (self._spawn_time + self._running_time + self._join_time)
        print("Total time for task %s %.3f sec:\n\t%.3f - *Build\n\t%.3f - Spawn\n\t%.3f - Running\n\t%.3f - Join\n\t%.3f - Service" %
              (self.name,  self._total_time, self._build_time, self._spawn_time, self._running_time, self._join_time, service_time))

        for name, block in self._block_factory.items():
            print("Block %s processed %d buffers" % (block.name, block.processed))


class TestTask(Task):
    # def __init__(self, name, **kw):
    #     super().__init__(name, **kw)

    def build(self, *args, **kwargs):
        gen = self.add(Generator("data_gen", (720, 1280, 3), max_rate=None))
        trans = self.add(Transformer("data_trans", 10))
        eat = self.add(Consumer("data_eat", "test"))

        # gen.sink = RingBuffer(1000)
        # trans.sink = RingBuffer(1000)
        # eat.sink = queue.Queue(maxsize=10000)
        eat.sink = mp.Queue(maxsize=100000)
        # eat.sink = self[2].producer
        # eat.source = self[2].client

        gen.child(trans, strategy=Source.Skip, skip=0).child(eat, strategy=Source.All)


if __name__ == '__main__':
    task = TestTask("test")

    files = []
    # pipe = task.spawn()
    task.start()
    while not task.ready.value:
        time.sleep(1e-6)

    task.remote(task.resume)
    print(task.remote(task.count, 10))
    print(task.remote(task.count))
    print(task.count(5))
    print(task.count(1))
    time.sleep(0.1)
    task.remote(task.pause)
    # task.pause()
    # task.resume()

    exit(0)

    t0 = time.time()
    # pipe.send("start")
    task._parent_pipe.send("start")

    while time.time() - t0 <= 0.1:
        while not task["data_eat"].sink.empty():
            files.append(task["data_eat"].sink.get()[0])
        time.sleep(1e-6)

    task._parent_pipe.send("stop")
    time.sleep(1e-3)
    task._parent_pipe.send("terminate")
    # time.sleep(3)
    # with task:
    #     time.sleep(0.1)

    task.join(auto_terminate=False)
    # task.print_stats()
    if task.exception:
        e = task.exception
        # e.__traceback__ = e[1]
        # raise e[0].with_traceback(e[1])
        print(e[1])
        raise e[0]

    while not task["data_eat"].sink.empty():
        files.append(task["data_eat"].sink.get()[0])
    print(len(files), "files", files)
