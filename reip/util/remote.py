'''

'''
import time
import random
import threading
import traceback
import warnings
import multiprocessing as mp
from ctypes import c_bool

__all__ = ['RemoteProxy']


FAIL_UNPICKLEABLE = False


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
    _delay = 0.1
    _not_forking = False  # queues and mp.value can only be pickled with forks
    def __init__(self, instance, *a, default=..., **kw):
        super().__init__(*a, **kw)
        self._obj = instance
        self._results = {}
        # self._local, self._remote = mp.Pipe()
        self._local, self._remote = mp.SimpleQueue(), mp.SimpleQueue()
        self._listening = mp.Value('i', 0, lock=False)
        self._default = default

        # NOTE: NOT WORKING ( ⚈̥̥̥̥̥́⌢⚈̥̥̥̥̥̀)

        # # this gets run on the fork before a process is run
        # mp.util.register_after_fork(self, self._after_fork)
        # # this is run after the process is run, as cleanup.
        # mp.util.Finalize(self, self.__class__._join, args=(self,), exitpriority=0)

    def __str__(self):
        return f'<Remote {self._obj} : {super().__str__()}>'

    def __getstate__(self):
        if self._not_forking:  # can't pickle queues or mp.Value except when forking
            return dict(self.__dict__, _thread=None, _listening=False,
                        _local=None, _remote=None)
        return dict(self.__dict__, _thread=None)  # can't pickle thread

    # def _after_fork(self):
    #     # automatically start listening thread when pickled and sent to a fork
    #     self.listen(block=False)

    # running state - to avoid dead locks, let the other process know

    def __nonzero__(self):
        return self.listening

    @property
    def listening(self):
        '''Is the remote instance listening?'''
        return bool(self._listening.value)

    @listening.setter
    def listening(self, value):
        self._listening.value = int(value)

    @property
    def is_main(self):  # TODO: cache this.
        '''Is the current process the main process or a child one?'''
        return mp.current_process().name == 'MainProcess'

    # internal view mechanics

    def _extend(self, *keys, **kw):
        obj = self.__class__.__new__(self.__class__)
        obj.__dict__.update(self.__dict__)
        RemoteView.__init__(obj, *self._keys, *keys, **kw)
        return obj

    def _as_view(self):
        '''Convert to a view so we don't pickle the object instance, just the keys.'''
        return RemoteView(*self._keys, frozen=True)

    # remote calling interface

    def listen(self, block=False):
        '''Start listening. By default, this will launch in a background thread.'''
        # print('Starting listening...', self, flush=True)
        return self._run() if block else self._spawn()

    def poll_until_clear(self):
        ''''''
        while not self._remote.empty():
            self.poll()

    def poll(self):
        '''Check for and execute the next command in the queue, if available.'''
        if not self._remote.empty():
            # get the called function
            result_id, view = self._remote.get()
            try:  # call the function and send the return value
                result = view.resolve_view(self._obj)
                # print(345345, view, result)
                try:
                    # can't pickle mp.Value outside of forking,
                    self._not_forking = True
                    self._local.put((result_id, result, None))
                    self._not_forking = False
                except RuntimeError as e:
                    if FAIL_UNPICKLEABLE:
                        warnings.warn(f'Return value of {view} is unpickleable.')
                        raise
                    warnings.warn(
                        f"You tried to send an unpickleable object returned by {view} "
                        "via a pipe. We'll assume this was an oversight and "
                        "will return `None`. The remote caller interface "
                        "is meant more for remote operations rather than "
                        "passing data. Check the return value for any "
                        "unpickleable objects. "
                        f"The return value: {result}")
            except BaseException as e:  # send any exceptions
                print(
                    f'An exception was raised in {self}.',
                    traceback.format_exc(), flush=True)
                self._local.put((result_id, None, e))

    def get_result(self, result_id, wait=True):
        # makes overlapping calls concurrency-safe
        while result_id not in self._results and self.listening:
            # print(result_id, self._results.keys(), self.listening, id(self), id(self._local), mp.current_process().pid)
            if not self._local.empty():
                out_id, x, exc = self._local.get()
                self._results[out_id] = x, exc
            elif not wait:
                break
            time.sleep(0.4)

        return self._results.pop(result_id, None)

    # parent calling interface

    def resolve(self, default=...):
        if self.is_main:
            return self.resolve_view(self._obj)
        if self.listening:
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
                if exc is not None:
                    raise Exception(f'Remote exception in {self._obj}') from exc
                return x

        # if a default value is provided, then return that, otherwise return a default.
        default = self._default if default is ... else default
        if default is ...:
            raise RuntimeError(f'Remote instance is not running for {self}')

        # warnings.warn(f'Remote instance is not running for {self._obj} - {self._as_view()}. '
        #               f'Returning default value `{default}`')
        return default


    @property
    def _(self):
        return self.resolve(None)

    # remote background listening interface

    def _spawn(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run)
            self._thread.daemon = True
            self._thread.start()
        return self

    def _join(self):
        self.listening = False
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        return self

    def _run(self):
        self.listening = True
        while self.listening:
            self.poll()
            time.sleep(self._delay)
        self.listening = False
        time.sleep(0.1)
        self.poll() # one last check in case of race condition? idk may delete.

    def __enter__(self):
        return self.listen()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._join()


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
        print(a.remote.asdf().asdf())
        print(a.remote.asdf().asdf()._)
        print(a.remote.x._, a.x, 40, 10, a.remote.x)
        print()

        print('local update')
        print(a.remote.asdf().asdf())
        print(a.asdf().asdf())
        print(a.remote.x._, a.x, 40, 40, a.remote.x)
        print()
        # test property accessing attribute works
        print('property')
        print(a.remote.zxcv._, a.zxcv, 4., 4., a.remote.zxcv)
        print()

        print('property')
        print(a.remote.super.zxcv._, super(type(a), a).zxcv, 8., 8., a.remote.super.zxcv)
        print()

        print('local update')
        a.terminate()
        print(a.remote.term._, a.term, False, True)
        a.start()
        print(a.remote.term._, a.term, False, False)
        print()

        print('remote update')
        a.remote.terminate()._
        print(a.remote.term._, a.term, True, False)
        a.remote.start()._
        print(a.remote.term._, a.term, False, False)
        print()
        print(flush=True)


    def _run(obj):  # some remote job
        # obj.remote.listen(block=True)
        while True:
            time.sleep(1)

    obj = _B()

    p = mp.Process(target=_run, args=(obj,), daemon=True)
    p.start()
    test(obj)
    # time.sleep(3)
    p.terminate()
    p.join()
