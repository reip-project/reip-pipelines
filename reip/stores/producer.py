from .pointers import Pointer
from ..interface import Sink
from .store import Store
from .plasma import PlasmaStore
from .client_store import ClientStore


class Producer(Sink):
    def __init__(self, size, delete_rate=5, context_id=None, **kw):
        self.size = size + 1  # need extra slot because head == tail means empty
        self.delete_rate = delete_rate
        self.context_id = context_id
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

    def spawn(self):
        for store in self.stores.values():
            if hasattr(store, 'spawn'):
                store.spawn()

    def join(self):
        for store in self.stores.values():
            if hasattr(store, 'join'):
                store.join()

    def full(self):
        self._trim()
        return (self.head.counter - self.tail.counter) >= (self.size - 1)

    def _trim(self):
        '''Delete any stale items from the queue.'''
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
        meta = meta or {}
        for store in self.stores.values():
            store.put(data, meta, id=self.head.pos)
        self.head.counter += 1

    def gen_source(self, context_id=None, throughput='small', **kw):
        '''Generate a source from this sink.

        Arguments:
            context_id (str): the identifier for the task.
            throughput (str): The size of data. This determines the serialization
                method to use. Should be:
                 - 'small' for data < 1GB
                 - 'medium' for data < 3GB
                 - 'large' for data > 3GB
            **kwargs: arguments to pass to `store.Customer`.
        '''
        # create the store if it doesn't exist already
        same_context = (
            context_id is None or self.context_id is None or
            context_id == self.context_id)
        store_id = same_context, throughput
        if store_id not in self.stores:  # use True/False as store keys
            if same_context:
                store = Store(self.size)
            else:
                if throughput == 'large':
                    store = PlasmaStore(self.size)
                else:
                    store = ClientStore(self.size)
                    if throughput == 'medium':
                        kw['faster_queue'] = True

                # convert pointers to shared pointers
                self.head = self.head.as_shared()
                self.tail = self.tail.as_shared()
            self.stores[store_id] = store

        # create a customer and a pointer.
        store = self.stores[store_id]
        self.readers.append(store.Pointer(self.size, self.tail.counter))
        return store.Customer(self, len(self.readers) - 1, store_id=store_id, **kw)
