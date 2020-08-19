'''

This is more of a general utility, than something directly relevant to reip.

I am using this in tests/test_stores.py.

Basically, what I want is to be able to decorate a function and handle
joining and raising exceptions when a result is finished.

This tries to replicate Concurrent Futures interface without building a pool.

I will pull this out into its own package and add it as a test dep.

'''
import time
import random
import traceback
import threading
import multiprocessing as mp


class DictQueue(mp.queues.SimpleQueue):
    _delay = 1e-6
    def __init__(self, *a, ctx=None, **kw):
        self._results = {}
        super().__init__(*a, ctx=ctx or mp.get_context(), **kw)

    def get(self, result_id=..., block=True):
        return (
            self._get_result(result_id, block=block) if result_id is not ...
            else super().get())

    def _get_result(self, result_id, block=True):
        '''Get the result from the queue. If there are overlapping calls, and
        if you pull the result meant for a different thread, save it to
        the results dictionary and keep pulling results until you get
        your result id.
        '''
        # NOTE: ripped from reip/util/remote.py
        while result_id not in self._results:
            if not self.empty():
                out_id, x = self.get()
                if out_id == result_id:
                    return x
                self._results[out_id] = x
            if not block:
                break
            time.sleep(self._delay)

        return self._results.pop(result_id, None)

    def put(self, x, id=None, **kw):
        return super().put((id, x), **kw)

class Future:
    def __init__(self, result_id, proc, q):
        self.result_id = result_id
        self.proc = proc
        self.queue = q
        self._last = ...

    def __str__(self):
        return f'<Future {self.result_id}>'

    def result(self):
        self.proc.join()
        if self._last is ...:
            self._last = res, exc = self.queue.get(self.result_id)
        else:
            res, exc = self._last
        if exc is not None:
            raise exc
        return res

class RemoteFunction:
    def __init__(self, func, threaded=False):
        self.func = func
        self._result_queue = DictQueue()
        self._cls = threading.Thread if threaded else mp.Process

    def __call__(self, *a, **kw):
        result_id = random.randint(0, 1000000000)
        p = self._cls(
            target=self._remote_run,
            args=(result_id, self.func) + a,
            kwargs=kw)
        f = Future(result_id, p, self._result_queue)
        p.start()
        return f

    def _remote_run(self, remote_id, func, *a, **kw):
        res, exc = None, None
        try:
            res = func(*a, **kw)
        except BaseException as e:
            exc = e
            print(traceback.format_exc())
        finally:
            self._result_queue.put((res, exc), id=remote_id)


def remote_func(__func__=None, *a, **kw):
    def inner(func):
        return RemoteFunction(func, *a, **kw)
    return inner(__func__) if callable(__func__) else inner


if __name__ == '__main__':
    def do_something(x):
        return x*2, mp.current_process().name, threading.current_thread().name

    do_something_remotely = remote_func(do_something)
    f = do_something_remotely(5)
    print(f)
    print(f.result())

    do_something_threaded = remote_func(do_something, threaded=True)
    f = do_something_threaded(6)
    print(f)
    print(f.result())

    def raise_something(x):
        raise ValueError
    raise_something_remotely = remote_func(raise_something)

    try:
        f = raise_something_remotely(5)
        print(f)
        print(f.result())
    except ValueError as e:
        print('raised', type(e), str(e))
    else:
        print('didnt raise an exception :(')
