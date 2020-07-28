import inspect
# from inspect import Parameter as Pm
import asyncio
from collections import ChainMap
import concurrent.futures


class Stack(ChainMap):
    '''Merged metadata dict stacks into one. Removes duplicates and empty maps.
    The original input maps can be accessed using `[d for d in stack.sources]`
    '''
    def __init__(self, *maps):
        super().__init__(*ordered_unique(flatten_maps(*maps)))
        self.sources = maps

    def update(self, *a, **kw):
        super().update(*a, **kw)
        return self


def flatten_maps(*metas):
    '''Flatten nested chain maps.'''
    for m in metas:
        if isinstance(m, ChainMap):
            yield from flatten_maps(*m.maps)
        elif m:
            yield m


def ordered_unique(maps):
    '''Remove duplicate maps (may happen due to branching+merging).'''
    ids = set()
    for m in maps:
        i = repr(m)
        if i not in ids:
            ids.add(i)
            yield m


###############################
# Ray-like Thread Executor
###############################

class LocalExecutor:
    '''Mimic ray's interface, but with threads.'''
    n_workers = 1
    def __init__(self, *a, **kw):
        self.__pool = concurrent.futures.ThreadPoolExecutor(self.n_workers)
        super().__init__(*a, **kw)

    def __str__(self):
        return '<LocalActor({})>'.format(super().__str__())

    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if not name.startswith('_LocalExecutor') and inspect.ismethod(value):
            # XXX: how to cache this or do this at the beginning ?
            return _PoolMethod(self.__pool, value)
        return value


class _PoolMethod:
    '''Wraps a method with a `.remote()` method.'''
    def __init__(self, pool, func):
        self._pool = pool
        self._func = func

    def __call__(self, *a, **kw):
        return self._func(*a, **kw)

    def remote(self, *a, **kw):
        return asyncio.wrap_future(self._pool.submit(self._func, *a, **kw))

    def __getattr__(self, name):
        return getattr(self._func, name)


def ray_local(cls, **kw):
    return type(cls.__name__, (LocalExecutor, cls), kw)




# POSARG_TYPES = [Pm.POSITIONAL_ONLY, Pm.POSITIONAL_OR_KEYWORD]
# ARG_TYPES = POSARG_TYPES + [Pm.KEYWORD_ONLY]
#
# def get_n_sources(f):
#     '''Get function parameters'''
#     sig = inspect.signature(f)
#     ps = sig.parameters.items()
#
#     args, vararg = [], False
#     for name, p in ps:
#         if name == 'meta':
#             break
#         if p.kind in POSARG_TYPES:
#             args.append(name)
#         elif p.kind == Pm.VAR_POSITIONAL:
#             vararg = True
#             break
#
#     return -1 if varargs else len(args)
#
#     args = [n for n, p in ps if p.kind in ARG_TYPES]
#     defaults = {n: p.default for n, p in ps if p.kind in ARG_TYPES}
#     posargs = [n for n, p in ps if p.kind in POSARG_TYPES]
#     posonlyargs = [n for n, p in ps if p.kind in POSARG_TYPES and
#                    p.default == inspect._empty]
#     vararg = next((n for n, p in ps if p.kind == Pm.VAR_POSITIONAL), None)
#     varkw = next((n for n, p in ps if p.kind == Pm.VAR_KEYWORD), None)
#     kwargs = {n: p.default for n, p in ps if p.default != inspect._empty}
#     return Spec(args, vararg, varkw, posargs, kwargs, posonlyargs, defaults)
