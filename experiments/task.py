from abc import ABC, abstractmethod
from interface import *
from block import *
import multiprocessing
import traceback
import queue
import time


class Task(ABC):
    def __init__(self, name, num_clients=0, num_producers=0):
        self.name = name
        self.clients = [None] * num_clients
        self.producers = [None] * num_producers

        self.ready = False
        self.running = False
        self.terminate = False
        self.error = False
        self.done = False

        self._block_factory = {}
        self._select = 0

        self._process = None
        self._debug = True
        self._verbose = True
        self._t0 = 0
        self._r0 = 0
        self._build_time = 0
        self._spawn_time = 0
        self._running_time = 0
        self._join_time = 0
        self._total_time = 0

    # Construction

    def add(self, block):
        if block.name in self._block_factory.keys():
            raise ValueError("Block %s already exists in task %s" % (block.name, self.name))
        else:
            self._block_factory[block.name] = block
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

    @property
    def client(self):
        return self.clients[self._select]

    @property
    def producer(self):
        return self.producers[self._select]

    @client.setter
    def client(self, new_client):
        if not issubclass(type(new_client), Source):
            if isinstance(new_client, queue.Queue):
                self.clients[self._select] = new_client
            else:
                raise ValueError("Not a client")
        else:
            self.clients[self._select] = new_client

    @producer.setter
    def producer(self, new_producer):
        if not issubclass(type(new_producer), Sink):
            if isinstance(new_producer, queue.Queue):
                self.producers[self._select] = new_producer
            else:
                raise ValueError("Not a producer")
        else:
            self.producers[self._select] = new_producer

    def child(self, other, **kw):
        if not issubclass(type(other), Task):
            raise ValueError("Not a task")
        if len(self.producers) == 0:
            raise ValueError("Task %s doesn't have any producers" % self.name)
        if len(other.clients) == 0:
            raise ValueError("Task %s doesn't have any clients" % other.name)
        else:
            other.client = self.producer.gen_source(**kw)
            return other

    def parent(self, other, **kw):
        return other.child(self, **kw)

    # Operation

    def build(self):
        pass

    def start(self):
        if not self.ready:
            raise RuntimeError("Task %s not ready to start" % self.name)
        else:
            self.running = True
            for name, block in self._block_factory.items():
                block.start()
            self._r0 = time.time()

    def __enter__(self):
        self.start()
        return self

    def stop(self):
        if not self.running:
            raise RuntimeError("Task %s not running" % self.name)
        else:
            self.running = False
            for name, block in self._block_factory.items():
                block.stop()
            self._running_time = time.time() - self._r0

    def __exit__(self, type, value, traceback):
        self.stop()
        return False

    def spawn(self, wait=True):
        for i, client in enumerate(self.clients):
            if client is None:
                raise RuntimeError("Client %d in task %s not connected" % (i, self.name))
        for i, producer in enumerate(self.producers):
            if producer is None:
                raise RuntimeError("Producer %d in task %s not connected" % (i, self.name))

        # self._process = multiprocessing.Process(target=self._run, name=self.name)
        self._process = threading.Thread(target=self._run, name=self.name)
        self._process.daemon = True
        if self._verbose:
            print("Spawning task %s..." % self.name)
        self.ready = False
        self.done = False
        self._process.start()

        if wait:
            while not self.ready:
                time.sleep(1e-6)

    def _run(self):
        try:
            self._t0 = time.time()
            self.build()
            self._build_time = time.time() - self._t0
            if self._verbose:
                print("Task %s Built in %.3f sec" % (self.name, self._build_time))

            s0 = time.time()
            for name, block in self._block_factory.items():
                block.spawn(wait=False)
            for name, block in self._block_factory.items():
                while not block.ready:
                    time.sleep(1e-6)
            self._spawn_time = time.time() - s0

            if self._verbose:
                print("Task %s Spawned in %.3f sec" % (self.name, self._spawn_time))
            self.ready = True
            # self.start()

            while not self.terminate:
                time.sleep(1e-6)

            j0 = time.time()
            for name, block in self._block_factory.items():
                block.terminate = True
            for name, block in self._block_factory.items():
                block.join()
            self._join_time = time.time() - j0

            self._total_time = time.time() - self._t0
            if self._verbose:
                print("Task %s Finished after %.3f sec" % (self.name, self._total_time))
            self.done = True
        except:
            self.error = True
            traceback.print_exc()

    def join(self, auto_terminate=True):
        if self._process is None:
            return

        if auto_terminate:
            self.terminate = True

        print("Joining task %s..." % self.name)
        self._process.join()
        if self._debug:
            print("Joined task", self.name)

    def print_stats(self):
        for name, block in self._block_factory.items():
            block.print_stats()
        service_time = self._total_time - (self._build_time + self._spawn_time + self._running_time + self._join_time)
        print("Total time for task %s %.3f sec:\n\t%.3f - Build\n\t%.3f - Spawn\n\t%.3f - Running\n\t%.3f - Join\n\t%.3f - Service" %
              (self.name,  self._total_time, self._build_time, self._spawn_time, self._running_time, self._join_time, service_time))

        for name, block in self._block_factory.items():
            print("Block %s processed %d buffers" % (block.name, block.processed))
