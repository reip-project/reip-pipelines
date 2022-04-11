import reip
import multiprocessing as mp
from reip.stores import Store, PlasmaStore, QueueStore, Pointer, Counter, HAS_PYARROW


class Producer(reip.Sink):
    def __init__(self, size=100, delete_rate=10, task_id=reip.UNSET, skip_no_readers=True, **kw):
        self.size = size + 1  # need extra slot because head == tail means empty
        self.delete_rate = delete_rate
        self.task_id = task_id
        self.stores = {}
        self.head = Pointer(self.size)
        self.tail = Pointer(self.size)
        self.skip_no_readers = skip_no_readers
        # self._dropped = Counter()
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

    def __len__(self):
        return self.head.counter - min(
            (r.counter for r in self.readers),
            default=self.tail.counter)

    def full(self):
        self._trim()
        return (self.head.counter - self.tail.counter) >= (self.size - 1)

    # @property
    # def dropped(self):
    #     return self._dropped.value
    #
    # @dropped.setter
    # def dropped(self, value):
    #     self._dropped.value = value

    def _trim(self):
        '''Delete any stale items from the queue.'''
        if self.readers:
            # get the number of stale entries
            new_value = min(
                (r.counter for r in self.readers),
                default=self.tail.counter)
            to_delete = [
                v % self.size for v in range(self.tail.counter, new_value)]

            # delete items if there's enough
            if len(to_delete) > self.size / self.delete_rate:
                # print("Trimming", len(to_delete))
                for store in self.stores.values():
                    store.delete(to_delete)
                self.tail.counter = new_value

    def _put(self, buffer):
        '''Send data to stores.'''
        if self.skip_no_readers and not self.readers:
            return
        data, meta = buffer
        meta = meta or {}
        for store in self.stores.values():
            store.put(data, meta, id=self.head.pos)
        self.head.counter += 1

    def gen_source(self, task_id=reip.UNSET, throughput='small', **kw):
        '''Generate a source from this sink.

        Arguments:
            task_id (str): the identifier for the task.
            throughput (str): The size of data. This determines the serialization
                method to use. Should be:
                 - 'small' for data < 1GB
                 - 'medium' for data < 3GB
                 - 'large' for data > 3GB
            **kwargs: arguments to pass to `store.Customer`.
        '''
        # create the store if it doesn't exist already
        same_context = (
            reip.UNSET.check(task_id) or reip.UNSET.check(self.task_id) or
            task_id == self.task_id)
        store_id = same_context, throughput
        if store_id not in self.stores:  # use True/False as store keys
            if same_context:
                store = Store(self.size)
            else:
                if HAS_PYARROW and throughput == 'large':
                    store = PlasmaStore(self.size)
                else:
                    store = QueueStore(self.size)
                    if HAS_PYARROW and throughput == 'medium':
                        kw.setdefault('serializer', 'arrow')

                # convert pointers to shared pointers
                self.head = self.head.as_shared()
                self.tail = self.tail.as_shared()
                # self._dropped = self._dropped.as_shared()
            self.stores[store_id] = store

        # create a customer and a pointer.
        store = self.stores[store_id]
        self.readers.append(store.Pointer(self.size, self.tail.counter))
        return store.Customer(self, len(self.readers) - 1, store_id=store_id, **kw)
