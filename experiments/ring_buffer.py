from interface import *
import numpy as np
import copy


class Pointer:
    def __init__(self, ring_size):
        self.counter = 0
        self.ring_size = ring_size

    @property
    def pos(self):
        return self.counter % self.ring_size

    @property
    def loop(self):
        return self.counter // self.ring_size


class RingBuffer(Sink):
    def __init__(self, size, **kw):
        self.size = size + 1  # need extra slot because head == tail means empty
        self.slots = [None] * self.size
        self.head = Pointer(self.size)
        self.tail = Pointer(self.size)
        self.readers = []
        super().__init__(**kw)

    def full(self):
        if len(self.readers) > 0:
            new_counter = min([reader.counter for reader in self.readers])
            for c in range(self.tail.counter, new_counter):
                self.slots[c % self.size] = None
            self.tail.counter = new_counter
            # self.tail.counter = min([reader.counter for reader in self.readers])
        return (self.head.counter - self.tail.counter) >= (self.size - 1)

    def _put(self, buffer):
        data, meta = buffer
        if isinstance(data, np.ndarray):
            data.flags.writeable = False
        self.slots[self.head.pos] = (data, ImmutableDict(meta))
        self.head.counter += 1

    def gen_source(self, **kw):
        self.readers.append(Pointer(self.size))
        self.readers[-1].counter = self.tail.counter
        return RingReader(self, len(self.readers) - 1, **kw)


class RingReader(Source):
    def __init__(self, ring, id, **kw):
        self.ring = ring
        self.id = id
        super().__init__(**kw)

    def empty(self):
        return self.ring.head.counter == self.ring.readers[self.id].counter

    def last(self):
        return (self.ring.head.counter - self.ring.readers[self.id].counter) <= 1

    def next(self):
        self.ring.readers[self.id].counter += 1

    def _get(self):
        return self.ring.slots[self.ring.readers[self.id].pos]
        # return copy.deepcopy(self.ring.slots[self.ring.readers[self.id].pos])


if __name__ == '__main__':
    rb = RingBuffer(100)

    print(issubclass(type(rb), Sink))

    r0 = rb.gen_source()
    r1 = rb.gen_source(strategy=Source.Skip, skip=1)
    r2 = rb.gen_source(strategy=Source.Latest)

    for i in range(10):
        rb.put((i, {}))

    print("r0:")

    while not r0.empty():
        print(r0.get()[0])
        r0.next()

    print("r1:")

    while not r1.empty():
        print(r1.get()[0])
        r1.next()

    print("r2:")

    while not r2.empty():
        print(r2.get()[0])
        r2.next()
