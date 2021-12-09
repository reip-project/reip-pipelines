'''Shortcuts for making a block.


.. code-block:: python

    # Make a block "MyBlock" that encapsulates init, process, and finish
    # inside one context manager

    @reip.make_block
    def MyBlock(block, add=10):
        try:
            ...  # self.init()
            def process(x, meta):
                return x + add, meta

            yield process
        finally:
            ...  # self.finish()

.. code-block:: python

    # Make a block "MyBlock" with only a process function

    @reip.make_block('process')
    def MyBlock(block, x, meta):
        if x == 1:
            return block.source_signals(reip.RETRY)
        return x, meta

    # Make a block "MyInit" with only an init function

    @reip.make_block('init')
    def MyInit(block):
        print("hello)


.. code-block:: python

    # Make a block "MyBlock" with both process and init functions.

    @reip.make_block('process')
    def MyBlock(block, x, meta):
        if x == 1:
            return block.source_signals(reip.RETRY)
        return x, meta

    @MyBlock.define('init')
    def MyBlock(block):
        print("hello)


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



# def asout(*values, meta=None):
#     return list(values), ({} if meta is None else meta)



# def asblock(__func__=None, n_inputs=None, meta=True, context=False, self=False, name=None, **kw):
#     def asblock_converter(func):
#         return type(name or func.__name__, (_BlockHelper,), {
#             '__init__': reip.util.partial(
#                 _BlockHelper.__init__, _func=func, _meta=meta,
#                 _context=context, _self=self, n_inputs=n_inputs, **kw)
#         })
#     return asblock_converter(__func__) if callable(__func__) else asblock_converter

# def asbasic(*a, meta=False, **kw):
#     '''Create a block using a process function that takes a single input and returns
#     a single output.

#     Example:
#     >>> TimesN = reip.helpers.asbasic(lambda x, n=2: x * n)  # creates a block
#     >>> B.Increment(5).to(TimesN(6)).to(B.Debug())  # 0 6 12 18 24
#     '''
#     return asblock(*a, single_output=True, meta=meta, **kw)

# def asmulti(*a, n_inputs=None, meta=False, **kw):
#     '''Create a block using a process function that takes multiple inputs and returns
#     a multiple inputs.

#     Example:
#     >>> Sum = reip.helpers.asmulti((lambda *xs: [sum(xs)]), n_inputs=None)  # creates a block
#     >>> B.Increment(5).to(Sum(6)).to(B.Debug())  # 0 6 12 18 24
#     >>> out = Sum()(B.Increment(12), B.Increment(10, 22))
#     '''
#     return asblock(*a, single_output=False, meta=meta, n_inputs=n_inputs, **kw)

# def asbasicmeta(*a, **kw):
#     return asblock(*a, single_output=True, meta=True, **kw)

# def asmultimeta(*a, **kw):
#     return asblock(*a, single_output=False, meta=True, **kw)

# def ascontext(*a, self=True, meta=True, single_output=False, **kw):
#     return asblock(*a, context=True, self=self, meta=meta, single_output=single_output, **kw)

# def asbasiccontext(*a, self=True, meta=False, single_output=True, **kw):
#     return asblock(*a, context=True, self=self, meta=meta, single_output=single_output, **kw)

# # internals


# def _wrap_process(meta=True):
#     '''Handle multiple output formats. Convert them to a uniform format.'''
#     def outer(func):
#         if single_output and meta:  # return x, meta => [x], meta
#             def inner(*a, **kw):
#                 x, meta = func(*a, **kw)
#                 return [x], meta
#             return functools.wraps(func)(inner)
#         if single_output and not meta:  # return x => [x], {}
#             return functools.wraps(func)(lambda *a, meta, **kw: ([func(*a, **kw)], {}))
#         if not single_output and not meta:  # return xs => xs, {}
#             return functools.wraps(func)(lambda *a, meta, **kw: (func(*a, **kw), {}))
#         return func  # return xs, meta
#     return outer

# def _wrap_context(func, context=False):
#     '''Wrap a process function and convert it to a context manager.'''
#     @functools.wraps(func)
#     def inner(*a, **kw):
#         yield reip.util.partial(func, *a, **kw)
#     return contextmanager(func if context else inner)


# class _BlockHelper(reip.Block):
#     def __init__(self, *a, _func, _single_output=False, _context=False, _meta=True, _self=False, **kw):
#         self.func = _func
#         self.__single_output = _single_output
#         self.__context = _context
#         self.__meta = _meta
#         self.extra_posargs = (self,)+a if _self else a
#         super().__init__(extra_kw=True, **kw)

#     _ctx = None
#     def init(self):
#         # ctx represents a context manager that does init and cleanup
#         func = _wrap_context(self.func, self.__context)
#         self._ctx = func(*self.extra_posargs, **self.extra_kw)
#         # context should yield the process function.
#         try:
#             process = self._ctx.__enter__()
#         except StopIteration as e:
#             raise RuntimeError('Block context function did not yield.') from e
#         self._process = _wrap_process(single_output=self.__single_output, meta=self.__meta)(process)

#     def process(self, *xs, meta):
#         return self._process(*xs, meta=meta)

#     def finish(self):
#         if self._ctx is not None:
#             self._ctx.__exit__(*sys.exc_info())
#         self._ctx = None



def make_block(__func_name__=None, __func__=None, name=None, cls=None, **clsdict):
    '''Make a block without writing out a full class.

    .. code-block:: python

        @reip.make_block
        def MyBlock(block, add=10):
            try:
                ...  # self.init()
                def process(x, meta):
                    return x + add, meta

                yield process
            finally:
                ...  # self.finish()

    .. code-block:: python

        @reip.make_block('process')
        def MyBlock(block, x, meta):
            if x == 1:
                return block.source_signals(reip.RETRY)
            return x, meta
    '''
    def inner(__func__, name=name, cls=cls):
        cls = reip.util.as_tuple(reip.Block if cls is None else cls)
        if __func__ is not None:
            name = name or __func__.__name__
            if __func_name__ is None:  # context function
                cls = (_ContextBlockMixin,) + cls
                clsdict['context'] = __func__
            else:  # one of init, process, finish
                clsdict[__func_name__] = __func__
        
        if not name:
            raise ValueError("No valid name provided for the block.")
        return type(name, cls, clsdict)

    # If it's a function directly, assume it's a context function
    if callable(__func_name__):
        __func__, __func_name__ = __func_name__, __func__
    return inner(__func__) if __func__ is not None else inner


class _ContextBlockMixin:
    def __init__(self, *a, **kw):
        self._get_context = contextmanager(self.context)
        self.extra_posargs = a
        super().__init__(extra_kw=True, **kw)

    _ctx = _process_function = None
    def init(self):
        try:  # ctx represents a context manager that does init and cleanup
            self._ctx = self._get_context(*self.extra_posargs, **self.extra_kw)
            self._process_function = self._ctx.__enter__()
        except StopIteration as e:
            raise RuntimeError('Block context function did not yield.') from e
        super().init()

    def process(self, *xs, meta):
        return self._process_function(*xs, meta=meta)

    def finish(self):
        if self._ctx is not None:
            self._ctx.__exit__(*sys.exc_info())
            self._ctx = None
        super().finish()

    def context(self):
        try:
            yield lambda *xs, meta: zip(xs, meta[:])
        finally:
            pass


class ContextBlock(_ContextBlockMixin, reip.Block):
    pass

class _ExtendBlockMethodsMixin:
    pass