'''

.. code-block:: python

    def something(x, y, z=1):
        print(x, y, z)
        time.sleep(5)
        return x + y + z

    with Thread(something)(5, 6) as th:
        time.sleep(3)
    assert th.result == 12

'''
from multiprocessing.queues import Queue
import time
import threading
import multiprocessing as mp


class _Base:
    def __init__(self, target, args=None, kwargs=None, *, daemon=True, name=None, before_close=None, return_result=True, timeout=60, group=None):
        super().__init__(target=target, args=args or (), kwargs=kwargs or {}, daemon=daemon, name=name, group=group)
        self._before_close = before_close
        self._join_timeout = timeout
        self._return_result = return_result
        # set a default name - _identity is set in __init__ so we have to
        # run it after
        if not name:
            self._name = '-'.join((s for s in (
                getattr(target, '__name__', None),
                self.__class__.__name__,
                ':'.join(str(i) for i in self._name.split('-')[1:])) if s))

    def __call__(self, *a, **kw):
        self._args = a
        self._kwargs = kw
        return self

    result = exception = None
    def start(self):
        self.q = self.QueueClass()
        self.result = self.exception = None
        super().start()
        return self

    _remote=False
    def run(self):
        _func2queue(
            self.q, self._target, *self._args, 
            _return_result=self._return_result, _remote=self._remote, 
            **self._kwargs)

    def join(self, timeout=None, raises=True):
        # this lets someone pass a function that will, say, do self.closing.set()
        if self._before_close:
            self._before_close()
        super().join(timeout=self._join_timeout if timeout is None else timeout)
        self.pull()
        if raises and self.exception is not None:
            raise self.exception

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.join()

    @property
    def result(self):
        if self._result is None and self.q is not None:
            self._result = queue_to_result(self.q)
        return self._result

    @result.setter
    def result(self, value):
        self._result = value

    def pull(self):
        while not self.q.empty():
            k, v = self.q.get()
            setattr(self, k, v)
        return self


import collections
class deQ(collections.deque):  # mimic a queue
    _delay = 1e-4
    def get(self, block=True):
        while block and not self:
            time.sleep(self._delay)
            continue
        return self.popleft()

    def put(self, x):
        self.append(x)

    def empty(self):
        return not self

class Thread(_Base, threading.Thread):
    QueueClass = deQ
    def throw(self, exc):
        raise_thread(exc, self)


__RESULT__ = 'result'
__EXCEPTION__ = 'exception'
__YIELD__ = 'yield'
__YIELD_CLOSE__ = 'yield-close'

class Process(_Base, mp.Process):
    QueueClass = mp.Queue
    _remote=True
    def run(self):
        try:
            super().run()
        finally:  # Avoid a refcycle
            del self._target, self._args, self._kwargs



def _func2queue(q, func, *a, _return_result=True, _remote=False, **kw):
    try:
        # call function
        x = func(*a, **kw)
        if not _return_result:  # discard result
            x = None
        if hasattr(x, '__iter__') and not hasattr(x, '__len__'):  # handle generator
            try:
                for xi in x:
                    q.put((__YIELD__, xi))
            finally:
                q.put((__YIELD_CLOSE__, None))
        else:  # handle normal result
            q.put((__RESULT__, x))
    except BaseException as e:
        if _remote:
            e = RemoteException(e)
        q.put((__EXCEPTION__, e))


def queue_to_result(q):
    def _gen(q):
        while True:
            k, v = q.get()
            if k == __EXCEPTION__:
                raise v
            yield k, v
    g = _gen(q)
    k, v = next(g)
    if k == __RESULT__:
        return v
    g = (x for xs in ([(k, v)], g) for x in xs)  # chain
    def _gen2():
        for k, v in g:
            if k == __YIELD_CLOSE__:
                return
            yield v
    return _gen2()



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


# https://github.com/python/cpython/blob/5acc1b5f0b62eef3258e4bc31eba3b9c659108c9/Lib/concurrent/futures/process.py#L127
class RemoteTraceback(Exception):
    def __init__(self, tb):
        self.tb = tb
    def __str__(self):
        return self.tb

class RemoteException:
    '''A wrapper for exceptions that will preserve their tracebacks
    when pickling. Once unpickled, you will have the original exception
    with __cause__ set to the formatted traceback.'''
    def __init__(self, exc):
        self.exc = exc
        self.tb = '\n```\n{}```'.format(''.join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ))
    def __reduce__(self):
        return _rebuild_exc, (self.exc, self.tb)

def _rebuild_exc(exc, tb):
    exc.__cause__ = RemoteTraceback(tb)
    return exc


if __name__ == '__main__':
    import time
    def something(x, y, z=1):
        print('started something', flush=True)
        time.sleep(1)
        print('finishing something', x, y, z, flush=True)
        return x + y + z
        
    def gen(x):
        for i in range(x):
            yield i
            time.sleep(0.2)

    def error():
        raise ValueError('asdfasdfasdf')

    for Agent in [Thread, Process]:
        print('class', Agent)

        t0 = time.time()
        with Agent(something)(5, 6, z=2) as th:
            print('started context', flush=True)
            time.sleep(0.1)
            print('finishing context', flush=True)
        print('joined', th.result, flush=True)
        assert th.result == 13

        with Agent(gen)(3) as th:
            for x in th.result:
                print(x)

        try:
            with Agent(error)() as th:
                pass
        except ValueError:
            import traceback
            traceback.print_exc()
