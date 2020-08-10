from .pointers import Pointer
from ..interface import Sink
from .store import Store
from .plasma import PlasmaStore
from .customer import Customer


class Producer(Sink):
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
        store = self.stores[same_context]
        self.readers.append(store.Pointer(self.size, self.tail.counter))
        return store.Customer(self, len(self.readers) - 1, **kw)
