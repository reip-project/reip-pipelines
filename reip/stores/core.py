import multiprocessing as mp
from .interface import Source
from reip.util import text


class Counter:
    def __init__(self, initial=0):
        self.value = initial

    def as_basic(self):
        return Counter(self.value)

    def as_shared(self):
        return SharedCounter(self.value)


class SharedCounter:
    def __init__(self, initial=0):
        self._value = mp.Value('i', initial, lock=False)
        super().__init__(initial)

    @property
    def value(self):
        return self._value.value

    @value.setter
    def value(self, new_value):
        self._value.value = new_value


class Pointer:
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

    def as_basic(self):
        return Pointer(self.size, self.counter)

    def as_shared(self):
        return SharedPointer(self.size, self.counter)


class SharedPointer(Pointer):
    def __init__(self, size, counter=0):
        self._counter = mp.Value('i', counter, lock=False)
        super().__init__(size, counter)

    @property
    def counter(self):
        return self._counter.value

    @counter.setter
    def counter(self, new_value):
        self._counter.value = new_value



class Customer(Source):
    def __init__(self, source, index, store_id, **kw):
        self.source = source
        self.id = index
        self.store_id = store_id
        super().__init__(**kw)

    def __str__(self):
        return '<{}[{}] queued={} {} of \n{}>'.format(
            self.__class__.__name__, self.id, len(self),
            self.source.readers[self.id],
            text.indent(self.source))

    def __len__(self):
        return self.source.head.counter - self.cursor.counter

    def next(self):
        if len(self):
            self.cursor.counter += 1

    def _get(self):
        return self.store.get(self.cursor.pos)

    @property
    def cursor(self):
        return self.source.readers[self.id]

    @property
    def store(self):
        return self.source.stores[self.store_id]


class BaseStore:
    Pointer = Pointer
    Customer = Customer

    def __str__(self):
        return '<{} n={}>'.format(self.__class__.__name__, len(self))

    def __len__(self):
        raise NotImplementedError

    def put(self, data, meta=None, id=None):
        raise NotImplementedError

    def get(self, id):
        raise NotImplementedError

    def delete(self, ids):
        raise NotImplementedError


class Store(BaseStore):
    def __init__(self, size):
        self.items = [None] * size

    def __len__(self):
        return len(self.items)

    def put(self, data, meta=None, id=None):
        self.items[id] = data, meta

    def get(self, id):
        return self.items[id]

    def delete(self, ids):
        for i in ids:
            self.items[i] = None
