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
import queue
import inspect
import threading
import traceback
import multiprocessing as mp

try:
    import dill as pickle
except ImportError:
    import pickle

class _Base:
    q = _result = exception = None
    _remote = False

    QueueClass = None
    EventClass = None

    def __init__(self, target, args=None, kwargs=None, *, daemon=False, name=None, before_close=None, return_result=True, timeout=60, group=None):
        super().__init__(target=target, args=args or (), kwargs=kwargs or {}, daemon=daemon, name=name, group=group)
        self._before_close = before_close
        self._join_timeout = timeout
        self._return_result = return_result
        self.finished = self.EventClass()
        # set a default name - _identity is set in __init__ so we have to
        # run it after
        if not name:
            self._name = '-'.join((s for s in (
                getattr(target, '__name__', None),
                self.__class__.__name__,
                ':'.join(str(i) for i in self._name.split('-')[1:])) if s))

    # interface

    def __call__(self, *a, **kw):
        self._args = a
        self._kwargs = kw
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.join()

    # core

    _target_is_generator = False
    def start(self):
        self.q = self.QueueClass()
        self.finished.clear()
        self._result = self.exception = None
        self._pulled = False
        self._target_is_generator = inspect.isgeneratorfunction(self._target)
        super().start()
        return self

    _remote=False
    def run(self):
        try:
            _func2queue(
                self.q, self._target, *self._args, 
                _return_result=self._return_result, _remote=self._remote, 
                **self._kwargs)
        finally:
            self.finished.set()

    def join(self, timeout=None, raises=True):
        # this lets someone pass a function that will, say, do self.closing.set()
        if self._before_close:
            self._before_close()
        super().join(timeout=self._join_timeout if timeout is None else timeout)
        self.pull()
        if raises and self.exception is not None:
            raise self.exception

    # get result
    
    @property
    def result(self):
        '''Get the result of the process function.'''
        if not self._pulled and self._result is None and self.q is not None:
            if self._target_is_generator or self.finished.is_set():
                self._result = queue_to_result(self.q)
                self._pulled = True
        return self._result

    @result.setter
    def result(self, value):
        self._result = value

    def pull(self):
        if self._result is None and self.q is not None and not self.q.empty():
            self._result = queue_to_result(self.q)
        return self

    @property
    def done(self):
        return self.finished.is_set()


# import collections
# class deQ(collections.deque):  # mimic a queue
#     _delay = 1e-4
#     def get(self, block=True):
#         while block and not self:
#             time.sleep(self._delay)
#             continue
#         return self.popleft()

#     def put(self, x):
#         self.append(x)

#     def empty(self):
#         return not self


from multiprocessing.queues import Queue as _MpQueue
class MpQueue(_MpQueue):
    """ A portable implementation of multiprocessing.Queue.
    https://gist.github.com/FanchenBao/d8577599c46eab1238a81857bb7277c9"""

    def __init__(self, *a, **kw):
        super().__init__(*a, ctx=mp.get_context(), **kw)
        self._size = mp.Value('i', 0)

    def __getstate__(self):
        return {'state': super().__getstate__(), 'size': self.size}

    def __setstate__(self, state):
        super().__setstate__(state['state'])
        self.size = state['size']

    def __inc(self, n=1):
        with self._size.get_lock():
            self._size.value += n

    def put(self, X, *a, **kw):
        super().put(pickle.dumps(X), *a, **kw)
        self.__inc(1)

    def get(self, *a, **kw):
        item = pickle.loads(super().get(*a, **kw))
        self.__inc(-1)
        return item

    def qsize(self):
        if self._closed:
            raise ValueError("queue is closed")
        return self._size.value

    def empty(self):
        return not self._size.value



class Thread(_Base, threading.Thread):
    QueueClass = queue.Queue #deQ
    EventClass = threading.Event
    def throw(self, exc):
        raise_thread(exc, self)


__RESULT__ = 'result'
__EXCEPTION__ = 'exception'
__YIELD__ = 'yield'
__YIELD_CLOSE__ = 'yield-close'

class Process(_Base, mp.Process):
    QueueClass = MpQueue #mp.Queue
    EventClass = mp.Event
    _remote=True
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

    def run(self):
        try:
            super().run()
        finally:  # Avoid a refcycle
            del self._target, self._args, self._kwargs



def _func2queue(__q, __func, *a, _return_result=True, _remote=False, **kw):
    '''Take a function and feed its result to a queue. This includes return values, 
    yield values, and exceptions.'''
    try:
        # call function
        x = __func(*a, **kw)
        if not _return_result:  # discard result
            x = None
        if hasattr(x, '__iter__') and not hasattr(x, '__len__'):  # handle generator
            try:
                for xi in x:
                    __q.put((__YIELD__, xi))
            finally:
                __q.put((__YIELD_CLOSE__, None))
        else:  # handle normal result
            __q.put((__RESULT__, x))
    except BaseException as e:
        if _remote:
            e = RemoteException(e)
            traceback.print_exception(type(e), e, e.__traceback__)
        __q.put((__EXCEPTION__, e))


def queue_to_result(q, timeout=6):
    def _gen(q):
        try:
            while True:
                # print('Getting process result')
                k, v = q.get(timeout=timeout)
                # print('k, v', k, v)
                if k == __EXCEPTION__:
                    raise v
                yield k, v
        except queue.Empty:
            pass
    g = _gen(q)
    try:
        k, v = next(g)
    except StopIteration:
        return
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
    def __init__(self, exc):
        self.tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        self.__cause__ = RemoteTraceback(exc.__cause__) if exc.__cause__ else None
        self.__context__ = RemoteTraceback(exc.__context__) if exc.__context__ else None

    def __str__(self):
        return f'\n```\n{"".join(self.tb)}```'

class RemoteException:
    '''A wrapper for exceptions that will preserve their tracebacks
    when pickling. Once unpickled, you will have the original exception
    with __cause__ set to the formatted traceback.'''
    def __init__(self, exc):
        self.exc = exc
        self.__cause__ = self.tb = RemoteTraceback(exc)
    def __reduce__(self):
        return _rebuild_exc, (self.exc, self.tb)

def _rebuild_exc(exc, tb):
    exc.__cause__ = tb
    return exc


# class RemoteException:
#     '''A wrapper for exceptions that will preserve their tracebacks
#     when pickling. Once unpickled, you will have the original exception
#     with __cause__ set to the formatted traceback.'''
#     def __init__(self, exc):
#         self.exc = exc
#     def __reduce__(self):
#         return _rebuild_exc, tb_dump(self.exc)

# def _rebuild_exc(exc, tb):
#     e = Exception()
#     e.__cause__ = tb_load(exc, tb)
#     return e

# class Traceback:
#     def __init__(self, tb):
#         self.tb_frame = Frame(tb.tb_frame) if tb.tb_frame is not None else None
#         self.tb_next = Traceback(tb.tb_next) if tb.tb_next is not None else None
#         self.tb_lasti = tb.tb_lasti    # 14
#         self.tb_lineno = tb.tb_lineno  # 6


# import sys
# from types import CodeType, TracebackType



# def tb_dump(exc):
#     tbs = []
#     tb = exc.__traceback__
#     while tb is not None:
#         tbs.append((tb.tb_frame.f_code.co_name, tb.tb_frame.f_lineno))
#         tb = tb.tb_next
#     print(tbs)
#     return exc, tbs[::-1]

# def tb_load(exc, tbs):
#     print(tbs)
#     tbs = [fake_traceback_frame(exc, None, *d) for d in tbs]
#     for t in tbs:
#         print(t)
#         print(''.join(traceback.format_tb(t)))
#     tb = tbs[0]
#     for t in tbs[1:]:
#         print(tb, t)
#         # tb = tb.tb_next = t
#         tb = t
#     return exc.with_traceback(tb)

# # https://github.com/pallets/jinja/blob/main/src/jinja2/debug.py
# def fake_traceback_frame(exc, tb: TracebackType=None, filename: str=None, lineno: int=0) -> TracebackType:
#     if tb:
#         tb = tb
#         filename = filename or tb.tb_frame.f_code.co_name
#         lineno = lineno or tb.tb_frame.f_lineno
#     locals = {}
#     globals = { "__name__": filename, "__file__": filename, "__exception__": exc }

#     # Raise an exception at the correct line number.
#     code = compile("\n" * (lineno - 1) + "raise __exception__", filename, "exec")

#     # Execute the new code, which is guaranteed to raise, and return
#     # the new traceback without this frame.
#     try:
#         exec(code, globals, locals)
#     except BaseException:
#         return sys.exc_info()[2].tb_next.tb_next


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
