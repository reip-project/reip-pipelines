from interface import *
from block import *
from stopwatch import StopWatch
from base import *
from dummies import *
import multiprocessing as mp
from ctypes import c_bool
import traceback
import queue
import time
import sys
import functools


class Task2(Manager, Worker, mp.Process):
    def __init__(self, name, manager=None, debug=True, verbose=False):
        mp.Process.__init__(self, target=self._run, name=name, daemon=True)
        Worker.__init__(self, name, manager=manager)  # overrides Process.name, Process.start() and Process.terminate()
        Manager.__init__(self)  # overrides Worker.__enter__() and Worker.__exit__() (< by order of inheritance ^)
        self._manager_conn, self._worker_conn = mp.Pipe()
        self.debug = debug
        self.verbose = verbose
        self._sw = StopWatch(name)
        self._was_running = False

    @property
    def exception(self):
        if self._manager_conn.poll():
            self._exception = self._manager_conn.recv()
        return self._exception

    def remote(self, func, *args, **kwargs):
        self._manager_conn.send((func.__name__, args, kwargs))
        ret = self._manager_conn.recv()
        if type(ret) is tuple and len(ret) == 2:
            if isinstance(ret[0], Exception) and type(ret[1]) is str:
                self._exception = ret[0]
                # print(RED + ret[1] + END)
                raise Exception("Remote exception in Task %s" % self.name) from ret[0]
        return ret

    def _poll(self):
        if self._worker_conn.poll():
            func, args, kwargs = self._worker_conn.recv()
            ret = getattr(self, func)(*args, **kwargs)
            self._worker_conn.send(ret)

    # Worker implementation

    def spawn(self, wait_ready=True):
        if self.verbose:
            print("Spawning task %s.." % self.name)

        self._ready.value, self._done.value = False, False
        self._running.value, self._terminate.value = False, False
        self._error.value, self._exception = False, None

        mp.Process.start(self)

        if wait_ready:
            while not self.ready:
                time.sleep(1e-5)

    def run(self):
        if self.verbose:
            print("Spawned task", self.name)

        try:
            mp.Process.run(self)
            self._worker_conn.send(None)
        except Exception as e:
            self._error.value, self._done.value = True, True
            self._exception = e
            tb = traceback.format_exc()
            print(RED + tb + END)
            try:
                self.join_all()
            except Exception as e2:
                print(RED + "Task %s failed to join blocks after ^ exception:\n" % self.name, e2, END)
            self._worker_conn.send((e, tb))
            # raise e  # You can still rise this exception if you need to

        if self.verbose:
            print("Exiting task %s.." % self.name)

    def _run(self):
        self._sw.tick()

        with self._sw("spawn"):
            self.spawn_all()

        if self.debug:
            print("Task %s spawned blocks in %.4f sec" % (self.name, self._sw["spawn"]))

        self._ready.value = True
        # self.start()

        while not self._terminate.value:
            if self.running:
                self.start_all()
                self._was_running = True
                with self._sw("running"):
                    time.sleep(1e-4)
            else:
                if self._was_running:
                    self.stop_all()
                    self._was_running = False
                with self._sw("waiting"):
                    time.sleep(1e-4)
            self._poll()

        with self._sw("join"):
            self.join_all()

        if self.debug:
            print("Task %s joined blocks in %.4f sec" % (self.name, self._sw["join"]))

        self._sw.tock()
        self._done.value = True

        if self.debug:
            print("Task %s Done after %.4f sec" % (self.name, self._sw[""]))

        while True:  # need better solution for preserving stats
            self._poll()

    def join(self, auto_terminate=True):
        if auto_terminate:
            self.terminate()

        mp.Process.join(self, timeout=0.1)

        if self.verbose:
            print("Joined task", self.name)

    # Manager implementation

    def get_stats(self):
        stats = Manager.get_stats(self)
        stats.append((self.name, self._sw))
        return stats

    def print_stats(self):
        Manager.print_stats(self)
        print(self._sw)


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

    def remote(self, func, *args, **kwargs):
        self._parent_pipe.send((func.__name__, args, kwargs))
        # handle exception
        return self._parent_pipe.recv()

    def resume(self):
        print("resume", self.name)
        self._start()

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
