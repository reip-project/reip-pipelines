import inspect
from inspect import Parameter as Pm
from collections import ChainMap


class Stack(ChainMap):
    '''Just in case we need to add extra functionality.'''
    def __init__(self, *maps):
        super().__init__(*ordered_unique(flatten_maps(*maps)))

    def update(self, *a, **kw):
        super().update(*a, **kw)
        return self


def flatten_maps(*metas):
    '''Flatten nested chain maps.'''
    for m in metas:
        if isinstance(m, Stack):
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


POSARG_TYPES = [Pm.POSITIONAL_ONLY, Pm.POSITIONAL_OR_KEYWORD]
ARG_TYPES = POSARG_TYPES + [Pm.KEYWORD_ONLY]

def get_n_sources(f):
    '''Get function parameters'''
    sig = inspect.signature(f)
    ps = sig.parameters.items()

    args, vararg = [], False
    for name, p in ps:
        if name == 'meta':
            break
        if p.kind in POSARG_TYPES:
            args.append(name)
        elif p.kind == Pm.VAR_POSITIONAL:
            vararg = True
            break

    return -1 if varargs else len(args)

    args = [n for n, p in ps if p.kind in ARG_TYPES]
    defaults = {n: p.default for n, p in ps if p.kind in ARG_TYPES}
    posargs = [n for n, p in ps if p.kind in POSARG_TYPES]
    posonlyargs = [n for n, p in ps if p.kind in POSARG_TYPES and
                   p.default == inspect._empty]
    vararg = next((n for n, p in ps if p.kind == Pm.VAR_POSITIONAL), None)
    varkw = next((n for n, p in ps if p.kind == Pm.VAR_KEYWORD), None)
    kwargs = {n: p.default for n, p in ps if p.default != inspect._empty}
    return Spec(args, vararg, varkw, posargs, kwargs, posonlyargs, defaults)
