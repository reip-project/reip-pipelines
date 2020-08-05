from interface import *
import multiprocessing as mp
import multiprocessing.queues
from ctypes import c_bool
import pyarrow as pa
import threading
import time


class FasterSimpleQueue(mp.queues.SimpleQueue):
    def get(self):
        with self._rlock:
            res = self._reader.recv_bytes()
        # unserialize the data after having released the lock
        # return _ForkingPickler.loads(res)
        return pa.deserialize(res)

    def put(self, obj):
        # serialize the data before acquiring the lock
        # obj = _ForkingPickler.dumps(obj)
        obj = pa.serialize(obj).to_buffer()
        if self._wlock is None:
            # writes to a message oriented win32 pipe are atomic
            self._writer.send_bytes(obj)
        else:
            with self._wlock:
                self._writer.send_bytes(obj)


class SharedPointer:
    def __init__(self, ring_size):
        self.counter = mp.Value('i', 0, lock=False)
        self.ring_size = ring_size

    @property
    def value(self):
        return self.counter.value

    @value.setter
    def value(self, new_value):
        self.counter.value = new_value

    @property
    def pos(self):
        return self.counter.value % self.ring_size

    @property
    def loop(self):
        return self.counter.value // self.ring_size


class Producer(Sink):
    def __init__(self, size, faster_queue=True, name="unknown", debug=False, **kw):
        self.name = name
        self.debug = debug
        self.faster_queue = faster_queue
        self.size = size + 1  # need extra slot because head == tail means empty
        self.slots = [None] * self.size
        self.head = SharedPointer(self.size)
        self.tail = SharedPointer(self.size)
        self.quit = mp.Value(c_bool, False, lock=False)
        self.clients = []
        self.thread = None
        super().__init__(**kw)

    def spawn(self):
        if self.debug:
            print("Spawning producer", self.name)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def join(self):
        if self.thread is not None:
            if self.debug:
                print("Joining producer", self.name)
            self.quit.value = True
            self.thread.join()
            self.thread = None
            if self.debug:
                print("Joined producer", self.name)

    def _run(self):
        if self.debug:
            print("Spawned producer", self.name)
        while not self.quit.value:
            for client in self.clients:
                if client.requested.value:
                    client.requested.value = False
                    client.data_queue.put(self.slots[client.pointer.pos])
            time.sleep(1e-6)
        if self.debug:
            print("Exiting producer", self.name)

    def full(self):
        if len(self.clients) > 0:
            new_value = min([client.pointer.value for client in self.clients])
            for v in range(self.tail.value, new_value):
                self.slots[v % self.size] = None
            self.tail.value = new_value
        return (self.head.value - self.tail.value) >= (self.size - 1)

    def _put(self, buffer):
        self.slots[self.head.pos] = buffer
        self.head.value += 1

    def gen_source(self, **kw):
        self.clients.append(Client(self, **kw))
        self.clients[-1].pointer.value = self.tail.value
        return self.clients[-1]


class Client(Source):
    def __init__(self, producer, **kw):
        self.requested = mp.Value(c_bool, False, lock=False)
        if producer.faster_queue:
            self.data_queue = FasterSimpleQueue(ctx=mp.get_context())
        else:
            self.data_queue = mp.SimpleQueue()
        self.producer = producer
        self.cache = None
        self.pointer = SharedPointer(producer.size)
        super().__init__(**kw)

    def empty(self):
        return self.producer.head.value == self.pointer.value

    def last(self):
        return (self.producer.head.value - self.pointer.value) <= 1

    def next(self):
        self.cache = None
        self.pointer.value += 1

    def _get(self):
        if self.cache is None:
            self.requested.value = True
            self.cache = self.data_queue.get()
        return self.cache


def run(clients):
    print("Started")
    [c0, c1, c2] = clients

    print("c0:")

    while not c0.empty():
        print(c0.get())
        c0.next()

    print("c1:")

    while not c1.empty():
        print(c1.get())
        c1.next()

    # bs.put((str(100), {"buffer": 100}))

    print("c2:")

    while not c2.empty():
        print(c2.get())
        c2.next()

    time.sleep(0.75)

    print("c2':")

    while not c2.empty():
        print(c2.get())
        c2.next()

    time.sleep(0.5)
    # raise RuntimeError("Foo")
    print("Done")


if __name__ == '__main__':
    p = Producer(100, debug=True)
    p.spawn()

    c0 = p.gen_source()
    c1 = p.gen_source(strategy=Source.Skip, skip=1)
    c2 = p.gen_source(strategy=Source.Latest)

    for i in range(10):
        p.put((str(i), {"buffer": i}))

    process = mp.Process(target=run, args=([c0, c1, c2], ))
    process.deamon = True
    process.start()

    time.sleep(0.5)

    p.put((str(200), {"buffer": 200}))

    process.join()
    p.join()
    time.sleep(0.1)
