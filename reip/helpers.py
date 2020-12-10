'''

# func_as_block : these are all equivalent

@reip.helpers.asblock(single_output=True, meta=False)
def basic_process_func(x, meta, n=2):
    return x * n

@reip.helpers.asblock(single_output=True)
def basic_process_func(x, meta, n=2):
    return x * n, {}

@reip.helpers.asblock(meta=False)
def basic_process_func(x, meta, n=2):
    return [x * n]

@reip.helpers.asblock()
def basic_process_func(x, meta, n=2):
    return [x * n], {}


# context_as_block (same variations apply for inner function)

@reip.helpers.asblock(single_output=True, meta=False, context=True)
def basic_process_func(n=2):
    def inner(x, meta):
        return x * n
    try:
        print('initialize')
        yield process
    finally:
        print('finish')
'''
import sys
import reip
import functools
import warnings
from contextlib import contextmanager


def asblock(__func__=None, single_output=False, meta=True, context=False, self=False, **kw):
    def asblock_converter(func):
        return reip.util.partial(
            _BlockHelper, func=func, __name__=func.__name__,
            single_output=single_output, meta=meta, context=context,
            _self=self, **kw)
    return asblock_converter(__func__) if callable(__func__) else asblock_converter

def asbasic(__func__, **kw):
    return asblock(single_output=True, meta=False, **kw)(__func__)

def asmulti(__func__, **kw):
    return asblock(single_output=False, meta=False, **kw)(__func__)

def asbasicmeta(__func__, **kw):
    return asblock(single_output=True, meta=True, **kw)(__func__)

def asmultimeta(__func__, **kw):
    return asblock(single_output=False, meta=True, **kw)(__func__)

def ascontext(__func__, self=True, meta=True, single_output=False, **kw):
    return asblock(context=True, self=self, meta=meta, single_output=single_output, **kw)(__func__)


# internals


def wrap_process(single_output=False, meta=True):
    '''Handle multiple output formats. Convert them to a uniform format.'''
    def outer(func):
        if single_output and meta:  # return x, meta => [x], meta
            def inner(*a, **kw):
                x, meta = func(*a, **kw)
                return [x], meta
            return functools.wraps(func)(inner)
        if single_output and not meta:  # return x => [x], {}
            return functools.wraps(func)(lambda *a, meta, **kw: ([func(*a, **kw)], {}))
        if not single_output and not meta:  # return xs => xs, {}
            return functools.wraps(func)(lambda *a, meta, **kw: (func(*a, **kw), {}))
        return func  # return xs, meta
    return outer

def _wrap_context(func, context=False):
    '''Wrap a process function and convert it to a context manager.'''
    @functools.wraps(func)
    def inner(*a, **kw):
        yield reip.util.partial(func, *a, **kw)
    return contextmanager(func if context else inner)


class _BlockHelper(reip.Block):
    def __init__(self, *a, func, single_output=False, context=False, meta=True, _self=False, **kw):
        self.func = func
        self.__single_output = single_output
        self.__context = context
        self.__meta = meta
        self.extra_posargs = (self,)+a if _self else a
        super().__init__(extra_kw=True, **kw)

    _ctx = None
    def init(self):
        # ctx represents a context manager that does init and cleanup
        func = _wrap_context(self.func, self.__context)
        self._ctx = func(*self.extra_posargs, **self.extra_kw)
        # context should yield the process function.
        try:
            process = self._ctx.__enter__()
        except StopIteration as e:
            raise RuntimeError('Block context function did not yield.') from e
        self._process = wrap_process(single_output=self.__single_output, meta=self.__meta)(process)

    def process(self, *xs, meta):
        return self._process(*xs, meta=meta)

    def finish(self):
        self._ctx.__exit__(*sys.exc_info())

