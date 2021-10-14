import threading


class Thread(threading.Thread):
    _result = _exception = None
    def __init__(self, __func, *a, daemon=True, thread_name=None, thread_close=None, thread_timeout=60, kwargs=None, **kw):
        super().__init__(__func, args=a, kwargs=dict(kw, **(kwargs or {})), daemon=daemon, name=thread_name)
        self._closer = thread_close
        self._join_timeout = thread_timeout
        # set a default name - _identity is set in __init__ so we have to
        # run it after
        if not thread_name:
            self._name = '-'.join((s for s in (
                getattr(__func, '__name__', None),
                self.__class__.__name__,
                ':'.join(str(i) for i in self._name.split('-')[1:])) if s))

    def run(self):
        self._result = self._exception = None
        try:
            x = self._target(*self._args, self._kwargs)
            self._result = x  # TODO: generators
        except BaseException as exc:
            self._exception = exc
        finally:  # Avoid a refcycle
            del self._target, self._args, self._kwargs

    def start(self):
        super().start()
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.join()

    def join(self, timeout=None, raises=True):
        # this lets someone pass a function that will, say, do self.closing.set()
        if self._closer:
            self._closer()
        super().join(timeout=self._join_timeout if timeout is None else timeout)

        if raises and self._exception is not None:
            raise self._exception

    def throw(self, exc):
        raise_thread(exc, self)


# import collections
# class Result(collections.deque):
#     def __init__(self):
#         super().__init__()
#         self.finished = False

#     def __iter__(self):
#         while not self.finished:
#             if not self:
#                 pass
#             yield self.popleft()

#     def consume(self, x, finished_on_error=True):
#         self.finished = False
#         try:
#             for xi in x:
#                 self.append(xi)
#         except Exception:
#             self.finished = bool(finished_on_error)
#         else:
#             self.finished = True


def raise_thread(exc, name='MainThread'):
    '''Raise an exception on another thread.
    https://gist.github.com/liuw/2407154
    # ref: http://docs.python.org/c-api/init.html#PyThreadState_SetAsyncExc
    Apparently this doesn't work in some cases:
    | if the thread to kill is blocked at some I/O or sleep(very_long_time)
    Maybe we can retry it or something?
    '''
    import ctypes
    tid = ctypes.c_long(find_thread(name, require=True).ident)
    ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exc))
    if ret == 0:
        raise ValueError("Invalid thread ID")
    if ret > 1:  # Huh? we punch a hole into C level interpreter, so clean up the mess.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)  # null
        raise SystemError("Raising in remote thread failed.")


def find_thread(name, require=False):
    '''Lookup a thread by name.'''
    if isinstance(name, threading.Thread):
        return name
    thr = next((t for t in threading.enumerate() if t.name == name), None)
    if require and thr is None:
        raise ValueError("Couldn't find thread matching: {}".format(name))
    return thr