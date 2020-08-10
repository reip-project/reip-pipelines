'''

Notes:
 - BufferStore now handles both same process and cross process sinks. It has
   either (or both) a DictStore and a PlasmaStore based on the sources connected.

 - For some reason.... You have to instantiate a new plasma client inside Customer._get.
   I don't know why this is happening.

   I assumed that it was a pickling error when forking the process and copying the plasma.connect object.
   So I added `__getstate__` and `__setstate__` to PlasmaStore, but that didn't work....
   (I still think that's the way to do this, but they're not being called.... asdjflkasdjflkasjdfl).

   As a work around, I added a `refresh` method to each store which will
   recreate the plasma client connection (and is a no-op for DictStore)

   Ideally, we should figure out and fix what's wrong and then remove that check in
   Customer._get, and the `refresh` methods.

'''
import time
import multiprocessing as mp
import pyarrow as pa
import pyarrow.plasma as plasma

from reip.util import text
from .plasma import PlasmaStore, random_object_id
from .interface import Source, Sink


class Pointer:
    same_context = True
    def __init__(self, size, counter=0):
        self.counter = counter
        self.size = size

    def __str__(self):
        return (
            f'<{self.__class__.__name__} i={self.counter} '
            f'pos={self.pos}/{self.size - 1} loop={self.loop}>')

    @property
    def pos(self):
        return self.counter % self.size

    @property
    def loop(self):
        return self.counter // self.size

    @property
    def store_id(self):
        return self.same_context

    def as_basic(self):
        return Pointer(self.size, self.counter)

    def as_shared(self):
        return SharedPointer(self.size, self.counter)


class SharedPointer(Pointer):
    same_context = False
    def __init__(self, size, counter=0):
        self._counter = mp.Value('i', counter, lock=False)
        super().__init__(size, counter)

    @property
    def counter(self):
        return self._counter.value

    @counter.setter
    def counter(self, new_value):
        self._counter.value = new_value


# def _pointer_type_converter(Type):
#     return lambda self: (
#         self if isinstance(self, Type)
#         else Type(self.size, self.counter))
# Pointer.as_basic = _pointer_type_converter(Pointer)
# Pointer.as_shared = _pointer_type_converter(SharedPointer)


class BufferStore(Sink):
    def __init__(self, size, delete_rate=5, **kw):
        self.size = size + 1  # need extra slot because head == tail means empty
        self.delete_rate = delete_rate
        self.stores = {}
        self.head = Pointer(self.size)
        self.tail = Pointer(self.size)
        self.readers = []
        super().__init__(**kw)

    def __str__(self):
        return '<{} \n  head={}\n  tail={}\n  readers={}\n  stores={}>'.format(
            self.__class__.__name__, self.head, self.tail,
            [str(p) for p in self.readers],
            [str(s) for s in self.stores.values()])

    def full(self):
        self._trim()
        return (self.head.counter - self.tail.counter) >= (self.size - 1)

    def _trim(self):
        if self.readers:
            # get the number of stale entries
            new_value = min(reader.counter for reader in self.readers)
            to_delete = [
                v % self.size for v in range(self.tail.counter, new_value)]

            # delete items if there's enough
            if len(to_delete) > self.size / self.delete_rate:
                for store in self.stores.values():
                    store.delete(to_delete)
                self.tail.counter = new_value

    def _put(self, buffer):
        '''Send data to stores.'''
        data, meta = buffer
        for store in self.stores.values():
            store.put(data, dict(meta or {}), id=self.head.pos)
        self.head.counter += 1

    def gen_source(self, same_context=True, **kw):
        # create the store if it doesn't exist already
        if same_context not in self.stores:  # use True/False as store keys
            self.stores[same_context] = (
                Store(self.size) if same_context else PlasmaStore(self.size))

            if not same_context:  # convert pointers to shared pointers if needed.
                self.head = self.head.as_shared()
                self.tail = self.tail.as_shared()

        # create a customer and a pointer.
        Pointer_ = Pointer if same_context else SharedPointer
        self.readers.append(Pointer_(self.size, self.tail.counter))
        return Customer(self, len(self.readers) - 1, **kw)


class Customer(Source):
    def __init__(self, source, index, **kw):
        self.source = source
        self.id = index
        super().__init__(**kw)

    def __str__(self):
        return '<{}[{}] {} of \n{}>'.format(
            self.__class__.__name__, self.id, self.source.readers[self.id],
            text.indent(self.source))

    def empty(self):
        return self.source.head.counter == self.source.readers[self.id].counter

    def last(self):
        return (self.source.head.counter - self.source.readers[self.id].counter) <= 1

    def next(self):
        self.source.readers[self.id].counter += 1

    def _get(self):
        reader = self.source.readers[self.id]
        return self.source.stores[reader.store_id].get(reader.pos)


class Store:
    def __init__(self, size):
        self.items = [None] * size

    def __str__(self):
        return '<{} n={}>'.format(self.__class__.__name__, len(self))

    def __len__(self):
        return len(self.items)

    def put(self, data, meta=None, id=None):
        self.items[id] = data, meta

    def get(self, id):
        return self.items[id]

    def delete(self, ids):
        for i in ids:
            self.items[i] = None


'''

Testing

'''



def run(customers):
    print("Started")
    [c0, c1, c2] = customers

    print("c0:", c0.strategy)

    while not c0.empty():
        print(c0.get())
        c0.next()

    print("c1:", c1.strategy)

    while not c1.empty():
        print(c1.get())
        c1.next()

    # bs.put((str(100), {"buffer": 100}))

    print("c2:", c2.strategy)

    while not c2.empty():
        print(c2.get())
        c2.next()

    time.sleep(0.75)

    print("c2':", c2.strategy)

    while not c2.empty():
        print(c2.get())
        c2.next()

    time.sleep(1.5)
    # raise RuntimeError("Foo")
    print("Done")


if __name__ == '__main__':
    import numpy as np
    bs = BufferStore(100)

    c0 = bs.gen_source(False)
    c1 = bs.gen_source(False, strategy=Source.Skip, skip=1)
    c2 = bs.gen_source(False, strategy=Source.Latest)

    print(issubclass(type(bs), Sink))
    print(bs.stores[False].client.store_capacity())
    print(bs.stores[False].client.list())
    bs.stores[False].client.delete(bs.stores[False].client.list())
    print(bs.stores[False].client.list())

    for i in range(10):
        bs.put((np.array([i]*4), {"buffer": i}))

    process = mp.Process(target=run, args=([c0, c1, c2], ), daemon=True)
    process.start()

    time.sleep(0.5)
    bs.put((np.array([200]*4), {"buffer": 200}))
    process.join()
