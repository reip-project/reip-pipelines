'''

TODO:
 - call Store.spawn, .join from Producer
 - test

'''
import time
import threading
import multiprocessing as mp
from ctypes import c_bool
from .pointers import Pointer, SharedPointer
from .store import Store
from .customer import Customer
from .queues import FasterSimpleQueue



class QueueCustomer(Customer):
    cache = None
    def __init__(self, *a, faster_queue=False, **kw):
        super().__init__(*a, **kw)
        self.requested = mp.Value(c_bool, False, lock=False)
        self.data_queue = (
            FasterSimpleQueue(ctx=mp.get_context()) if faster_queue else
            mp.SimpleQueue())
        self.store.customers.append(self)  # circular reference - garbage collection issue?

    def next(self):
        self.cache = None
        super().next()

    def _get(self):
        if self.cache is None:
            self.requested.value = True
            self.cache = self.data_queue.get()
        return self.cache


# class QueuePointer(SharedPointer):
#     cache = None
#     def __init__(self, size, counter=0, faster_queue=False):
#         super().__init__(size, counter)
#         self.requested = mp.Value(c_bool, False, lock=False)
#         self.data_queue = (
#             FasterSimpleQueue(ctx=mp.get_context()) if faster_queue else
#             mp.SimpleQueue()
#         )
#
#     def _get(self):
#         if self.cache is None:
#             self.requested.value = True
#             self.cache = self.data_queue.get()
#         return self.cache



class ClientStore(Store):
    Pointer = SharedPointer
    Customer = QueueCustomer

    debug = False
    _thread = None
    def __init__(self, *a, **kw):
        self.customers = []
        self.quit = mp.Value(c_bool, False, lock=False)
        super().__init__(*a, **kw)

    def spawn(self):
        if self.debug:
            print("Spawning producer", self)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def join(self):
        if self._thread is not None:
            if self.debug:
                print("Joining producer", self)
            self.quit.value = True
            self._thread.join()
            self._thread = None
            if self.debug:
                print("Joined producer", self)

    def _run(self):
        if self.debug:
            print("Spawned producer", self)
        while not self.quit.value:
            for c in self.customers:
                if c.requested.value:
                    c.requested.value = False
                    c.data_queue.put(self.items[c.cursor.pos])
            time.sleep(1e-6)
        if self.debug:
            print("Exiting producer", self)
