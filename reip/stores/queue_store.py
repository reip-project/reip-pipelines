'''

'''
import time
import threading
import multiprocessing as mp
from ctypes import c_bool
import remoteobj
from . import SharedPointer, Store, Customer, Queue


class _RemoteTraceback(Exception):
    def __init__(self, tb):
        self.tb = tb
    def __str__(self):
        return self.tb

class QueueCustomer(Customer):
    '''A customer that requests values from a Queue Store.'''
    cache = None
    def __init__(self, *a, serializer=None, **kw):
        super().__init__(*a, **kw)
        self.requested = mp.Value(c_bool, False, lock=False)
        self.data_queue = Queue(serializer)
        self.store.customers.append(self)  # circular reference - garbage collection issue?

    def empty(self):
        return self.store.quit.value or super().empty()

    def next(self):
        self.cache = None
        super().next()

    def _get(self):
        if self.cache is None:
            if not self.store.error.value:
                if self.store.quit.value:
                    raise RuntimeError('Store is not running.')
                self.requested.value = True
                v = self.data_queue.get()
            if self.store.error.value:
                exc = RuntimeError('Exception {} in {}'.format(v[0], self.store.__class__.__name__))
                exc.__cause__ = _RemoteTraceback(v[1])
                raise exc
            self.cache = v
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



class QueueStore(Store):
    '''A Store that will push values through a queue when a Customer requests.'''
    Pointer = SharedPointer
    Customer = QueueCustomer

    debug = False
    _thread = None
    def __init__(self, *a, **kw):
        self.customers = []
        self.quit = mp.Value(c_bool, False, lock=False)
        self.error = mp.Value(c_bool, False, lock=False)
        super().__init__(*a, **kw)

    def spawn(self):
        if self.debug:
            print("Spawning producer", self)
        self.quit.value = self.error.value = False
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
                    try:
                        c.requested.value = False
                        c.data_queue.put(self.items[c.cursor.pos])
                    except Exception as e:
                        self.error.value = True
                        import traceback
                        c.data_queue.put((type(e).__name__, traceback.format_exc()))
            time.sleep(1e-6)
        if self.debug:
            print("Exiting producer", self)
