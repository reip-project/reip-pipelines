from interface import *
from plasma import save_data, load_data, save_meta, load_meta
import pyarrow as pa
import numpy as np
import pyarrow.plasma as plasma
import multiprocessing as mp
import time
import copy


class UniqueID:
    _id = 0

    @staticmethod
    def Gen():
        UniqueID._id += 1
        t = "%20s" % str(UniqueID._id)
        print(t.encode("utf-8"))
        return plasma.ObjectID(t.encode("utf-8"))


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


class BufferStore(Sink):
    def __init__(self, size, **kw):
        self.size = size + 1  # need extra slot because head == tail means empty
        self.data_ids = [UniqueID.Gen() for i in range(self.size)]
        self.meta_ids = [UniqueID.Gen() for i in range(self.size)]
        self.head = SharedPointer(self.size)
        self.tail = SharedPointer(self.size)
        self.customers = []
        self.pipes = []
        self.client = plasma.connect("/tmp/plasma")
        print("Store Connected")
        super().__init__(**kw)

    def full(self):
        if len(self.customers) > 0:
            new_value = min([customer.value for customer in self.customers])

            to_delete = []
            for v in range(self.tail.value, new_value):
                to_delete.append(self.data_ids[v % self.size])
                to_delete.append(self.meta_ids[v % self.size])

            if len(to_delete) > 0:
                print("Deleting:", to_delete)
                self.client.delete(to_delete)
                self.tail.value = new_value

        return (self.head.value - self.tail.value) >= (self.size - 1)

    def _put(self, buffer):
        data, meta = buffer

        save_data(self.client, data, id=self.data_ids[self.head.pos])
        save_meta(self.client, meta, id=self.meta_ids[self.head.pos])

        self.head.value += 1

    def gen_source(self, **kw):
        self.customers.append(SharedPointer(self.size))
        self.customers[-1].value = self.tail.value
        return Customer(self, len(self.customers) - 1, **kw)


class Customer(Source):
    def __init__(self, store, id, **kw):
        self.store = store
        self.id = id
        self.client = None
        super().__init__(**kw)

    def empty(self):
        return self.store.head.value == self.store.customers[self.id].value

    def last(self):
        return (self.store.head.value - self.store.customers[self.id].value) <= 1

    def next(self):
        self.store.customers[self.id].value += 1

    def _get(self):
        if self.client is None:
            self.client = plasma.connect("/tmp/plasma")
            print("Customer Connected")

        data = load_data(self.client, self.store.data_ids[self.store.customers[self.id].pos])
        meta = load_meta(self.client, self.store.meta_ids[self.store.customers[self.id].pos])

        return data, meta


def run(customers):
    print("Started")
    [c0, c1, c2] = customers

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

    time.sleep(1.5)
    # raise RuntimeError("Foo")
    print("Done")


if __name__ == '__main__':
    bs = BufferStore(100)

    print(issubclass(type(bs), Sink))
    print(bs.client.store_capacity())
    print(bs.client.list())
    bs.client.delete(bs.client.list())
    print(bs.client.list())

    c0 = bs.gen_source()
    c1 = bs.gen_source(strategy=Source.Skip, skip=1)
    c2 = bs.gen_source(strategy=Source.Latest)

    for i in range(10):
        bs.put((str(i), {"buffer": i}))

    process = mp.Process(target=run, args=([c0, c1, c2], ))
    process.deamon = True
    process.start()

    time.sleep(0.5)

    bs.put((str(200), {"buffer": 200}))

    process.join()

    time.sleep(5)
