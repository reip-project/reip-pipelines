'''


Usage:
>>> class MyObj:
...     def __init__(self):
...         self.remote = RemoteProxy(self)
...         self.stopped = False
...         self.data = []
...
...     def stop(self):
...         self.stopped = True
...
...     def get_data(self):
...         while not self.stopped:
...             self.data.append(time.time())
...             time.sleep(1)

>>> obj = MyObj()
>>> p = mp.Process(target=obj.get_data)
>>> p.start()
>>> time.sleep(3)
>>> obj.remote.stop()
>>> p.join()

'''
import time
import random
import threading
import traceback
import warnings
import multiprocessing as mp
import reip

__all__ = ['RemoteProxy']


FAIL_UNPICKLEABLE = False
SELF = reip.make_token('self')


def retrieve(view, **kw):
    return view.retrieve(**kw)


class RemoteView:
    '''Represents a set of operations that can be captured, pickled, and
    applied to a remote object.

    This supports things like:
        - `view.some_attribute`
            NOTE: this doesn't work with private or magic attributes
        - `view['some key']`
        - `view(1, 2, x=10)`
        - `view.some_method(1, 2)`
        - `view.super.some_method(1, 2)`
                (translates to `super(type(obj), obj).some_method(1, 2)`)

    '''
    _keys, _frozen = (), False
    def __init__(self, *keys, frozen=False):
        self._keys = keys
        self._frozen = frozen

    def __str__(self):
        '''Return a string representation of the Op.'''
        x = '?'
        for kind, k in self._keys:
            if kind == '.':
                if k == 'super':
                    x = f'super({x})'
                else:
                    x = f'{x}.{k}'
            elif kind == '[]':
                x = f'{x}[{x!r}]'
            elif kind == '()':
                args = ', '.join(
                    [f'{a:!r}' for a in k[0]] +
                    [f'{ka}={a!r}' for ka, a in k[1].items()])
                x = f'{x}({args})'
        return f'({x})'

    def resolve_view(self, obj):
        '''Given an object, apply the view - get nested attributes, keys, call, etc.'''
        orig = obj
        for kind, k in self._keys:
            if kind == '.':
                if k == 'super':
                    obj = super(type(obj), obj)
                else:
                    obj = getattr(obj, k)
            elif kind == '[]':
                obj = obj[k]
            elif kind == '()':
                obj = obj(*k[0], **k[1])
        return obj

    def _extend(self, *keys, **kw):
        '''Return a copy of self with additional keys.'''
        return RemoteView(*self._keys, *keys, **kw)

    def __getattr__(self, name):
        '''Append a x.y op.'''
        if name.startswith('_') or self._frozen:
            raise AttributeError(name)
        return self._extend(('.', name))

    def __getitem__(self, index):
        '''Append a x[1] op.'''
        if self._frozen:
            raise KeyError(index)
        return self._extend(('[]', index))

    def __call__(self, *a, **kw):
        '''Append a x(1, 2) op.'''
        if self._frozen:
            raise TypeError(f'{self} is frozen and is not callable.')
        return self._extend(('()', (a, kw)))


class RemoteProxy(RemoteView):
    '''Capture and apply operations to a remote object.

    Usage:


    '''
    _thread = None
    _delay = 1e-5
    def __init__(self, instance, *a, default=..., **kw):
        super().__init__(*a, **kw)
        self._obj = instance
        self._results = {}
        # self._local, self._remote = mp.Pipe()
        self._local, self._remote = mp.SimpleQueue(), mp.SimpleQueue()
        self._local_name = mp.current_process().name
        self._listening = mp.Value('i', 0, lock=False)
        self._default = default

    def __str__(self):
        return f'<Remote {self._obj} : {super().__str__()}>'

    def __getstate__(self):
        '''Don't pickle queues, locks, and shared values.'''
        return dict(self.__dict__, _thread=None, _listening=False,
                    _local=None, _remote=None)

    @property
    def is_local(self):
        '''Is the current process the main process or a child one?'''
        return mp.current_process().name == self._local_name

    # internal view mechanics. These override RemoteView methods.

    def _extend(self, *keys, **kw):
        # Create a new remote proxy object. Don't call RemoteProxy.__init__
        obj = self.__class__.__new__(self.__class__)
        obj.__dict__.update(self.__dict__)
        RemoteView.__init__(obj, *self._keys, *keys, **kw)
        return obj

    def _as_view(self):
        '''Convert to a view so we don't pickle the object instance, just the keys.'''
        return RemoteView(*self._keys, frozen=True)

    def __call__(self, *a, default=..., **kw):
        '''Automatically retrieve when calling a function.'''
        # You can no longer chain functions. They automatically retrieve.
        return super().__call__(*a, **kw).retrieve(default=default)

    # remote calling interface

    def poll_until_clear(self):
        '''Poll until the command queue is empty.'''
        while not self._remote.empty():
            self.poll()

    def poll(self):
        '''Check for and execute the next command in the queue, if available.'''
        if not self._remote.empty():
            # get the called function
            result_id, view = self._remote.get()
            try:  # call the function and send the return value
                result = view.resolve_view(self._obj)
            except BaseException as e:  # send any exceptions
                print(
                    f'An exception was raised in {self}.',
                    traceback.format_exc(), flush=True)
                self._local.put((result_id, None, e))

            try:
                if result is self._obj:  # solution for chaining
                    result = SELF
                self._local.put((result_id, result, None))
            except RuntimeError as e:
                if FAIL_UNPICKLEABLE:
                    warnings.warn(f'Return value of {view} is unpickleable.')
                    raise
                warnings.warn(
                    f"You tried to send an unpickleable object returned by {view} "
                    "via a pipe. We'll assume this was an oversight and "
                    "will return `None`. The remote caller interface "
                    "is meant more for remote operations rather than "
                    "passing objects. Check the return value for any "
                    "unpickleable objects. "
                    f"The return value: {result}")

    # parent calling interface

    def retrieve(self, default=...):
        if not self.is_local:  # if you're in the main thread, just run the function.
            return self.resolve_view(self._obj)
        if self.listening:  # if the remote process is listening, run
            # send command and wait for response
            result_id = random.randint(0, 10000000)
            view = self._as_view()

            self._remote.put((result_id, view))
            result = self.get_result(result_id)

            # if no result was returned, the queue was probably closed before
            # being able to execute the request.
            if result is not None:  # valid results are tuples
                # raise any exceptions returned
                x, exc = result
                if result == SELF:
                    result = self
                if exc is not None:
                    raise Exception(f'Remote exception in {self._obj}') from exc
                return x

        # if a default value is provided, then return that, otherwise return a default.
        default = self._default if default is ... else default
        if default is ...:
            raise RuntimeError(f'Remote instance is not running for {self}')
        return default

    def get_result(self, expected_id, wait=True):
        while self.listening:
            if not self._local.empty():
                out_id, x, exc = self._local.get()
                assert expected_id == out_id  # safety check
                return x, exc
            if not wait:
                break
            time.sleep(self._delay)


    # def get_result(self, result_id, wait=True):
    #     '''Get the result from the queue. If there are overlapping calls, and
    #     if you pull the result meant for a different thread, save it to
    #     the results dictionary and keep pulling results until you get
    #     your result id.
    #     '''
    #     # makes overlapping calls concurrency-safe
    #     while result_id not in self._results and self.listening:
    #         if not self._local.empty():
    #             out_id, x, exc = self._local.get()
    #             if out_id is result_id:
    #                 return x, exc
    #             self._results[out_id] = x, exc
    #         if not wait:
    #             break
    #         time.sleep(self._delay)
    #
    #     return self._results.pop(result_id, None)

    ########################################################################
    # If we don't want to poll for commands in the background and we
    # want all commands to happen in the main thread, then we can remove
    # the methods below.
    ########################################################################

    # running state - to avoid dead locks, let the other process know if you will respond

    def wait_until_listening(self, timeout=None):
        t0 = time.time()
        while not self.listening:
            if timeout and time.time() - t0 > timeout:
                raise TimeoutError('Waiting for remote {} instance to listen timed out.'.format(self))
            time.sleep(self._delay)

    @property
    def listening(self):
        '''Is the remote instance listening?'''
        return bool(self._listening.value)

    @listening.setter
    def listening(self, value):
        self._listening.value = int(value)

    def __enter__(self):
        self.listening = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.listening = False


    # remote background listening interface

    # def listen(self, block=False):
    #     '''Start listening. By default, this will launch in a background thread.'''
    #     # print('Starting listening...', self, flush=True)
    #     return self._run() if block else self._spawn()
    #
    # def _spawn(self):
    #     if self._thread is None:
    #         self._thread = threading.Thread(target=self._run)
    #         self._thread.daemon = True
    #         self._thread.start()
    #     return self
    #
    # def _join(self):
    #     self.listening = False
    #     if self._thread is not None:
    #         self._thread.join()
    #         self._thread = None
    #     return self
    #
    # def _run(self):
    #     self.listening = True
    #     while self.listening:
    #         self.poll()
    #         time.sleep(self._delay)
    #     self.listening = False
    #     time.sleep(0.1)
    #     self.poll() # one last check in case of race condition? idk may delete.
    #
    # def __enter__(self):
    #     return self.listen()
    #
    # def __exit__(self, exc_type, exc_val, exc_tb):
    #     self._join()


# def _find_type_matching(module_name):
#     objs = {}
#     for



'''

Tests

'''


class _A:
    x = 10
    term = False
    def __init__(self):
        self.remote = RemoteProxy(self)

    def __str__(self):
        return f'<A x={self.x} terminated={self.term}>'

    def asdf(self):
        self.x *= 2
        return self

    @property
    def zxcv(self):
        return self.x / 5.

    def terminate(self):
        self.term = True
        return self

    def start(self):
        self.term = False
        return self

class _B(_A):
    @property
    def zxcv(self):
        return self.x / 10.


if __name__ == '__main__':
    def test(a):
        print('str format')
        print(a.remote)
        print(a.remote.x)
        print(a.remote.asdf().asdf().zxcv)
        print()

        # test basic attribute
        print('attribute')
        print(a.remote.x._, a.x, 10, a.remote.x)
        print()
        # test attribute, call, return self
        print('remote update')
        print(a.remote.asdf())
        print(a.remote.asdf())
        print(a.remote.x.retrieve(), a.x, 20, 20, a.remote.x)
        print()

        print('local update')
        print(a.remote.asdf())
        print(a.asdf())
        print(a.remote.x.retrieve(), a.x, 40, 40, a.remote.x)
        print()
        # test property accessing attribute works
        print('property')
        print(a.remote.zxcv.retrieve(), a.zxcv, 4., 4., a.remote.zxcv)
        print()

        print('property')
        print(a.remote.super.zxcv.retrieve(), super(type(a), a).zxcv, 8., 8., a.remote.super.zxcv)
        print()

        print('local update')
        a.terminate()
        print(a.remote.term.retrieve(), a.term, False, True)
        a.start()
        print(a.remote.term.retrieve(), a.term, False, False)
        print()

        print('remote update')
        a.remote.terminate()
        print(a.remote.term.retrieve(), a.term, True, False)
        a.remote.start()
        print(a.remote.term.retrieve(), a.term, False, False)
        print()
        print(flush=True)


    def _run(obj):  # some remote job
        # obj.remote.listen(block=True)
        while True:
            obj.remote.poll()
            time.sleep(0.0001)

    obj = _B()

    p = mp.Process(target=_run, args=(obj,), daemon=True)
    p.start()
    test(obj)
    # time.sleep(3)
    p.terminate()
    p.join()
