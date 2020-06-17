'''
Block Utilities
===============


'''

import readi
import fnmatch


def make_glue(kw):
    '''Define a data transformation function for either the input or output of
    a block. Assumes input and desired output are dictionaries.

    Examples:
        inputs:
            one_key: True
            second_key:
            new_name:
                source: third_key
                slice:

        inputs = make_glue(cfg)
        kw_mod = inputs(kw)
    '''
    if kw is False: # inputs: False
        return lambda x: {}
    if kw is True or kw is None: # inputs: True
        return lambda x: x
    if isinstance(kw, str): # inputs: key_a, key_b
        kw = {s.strip(): True for s in kw.split(',')}
    elif isinstance(kw, (list, tuple)): # inputs: ['key_a', 'key_b']
        kw = {s: True for s in kw}

    def formatter(slice=None):
        slc = to_slice(slice) if slice is not None else slice
        def inner(x):
            if slc is not None:
                x = x[slc]
            return x
        return inner

    outs = {}
    for k, v in kw.items():
        if v is True or v is None:
            v = {}
        if isinstance(v, (str, list, tuple)):
            v = {'slice': to_slice(v)}
        outs[k] = (v.pop('source', k), formatter(**v))

    def glue(x):
        if not isinstance(x, dict):
            return {k_new: func(x) for k, (k_new, func) in outs.items()}
        return {
            k_new: func(vi)
            for k, (k_new, func) in outs.items()
            for ki, vi in x.items()
            if fnmatch.fnmatch(k, ki)
        }

    return glue


def to_slice(x):
    xs = (x.strip() for x in str(x).split(','))
    xs = ((xi.strip() for xi in x.split(':')) for x in xs)
    xs = (
        [SLICE_TOKENS[x] if x in SLICE_TOKENS
         else int(x) if x else None for xi in x]
        for x in xs)
    return tuple(
        slice(*x) if len(x) > 1 else x[0] if len(x) else slice(None, None)
        for x in xs)

SLICE_TOKENS = {'...': ..., 'None': None, 'null': None, '': None}


def tee_blocks(blocks, config, **kw):
    if not blocks:
        return []
    is_single = isinstance(blocks, dict)
    blocks = [blocks] if is_single else blocks
    blocks = [config.get_block(**kw, **bl) for bl in blocks]
    return blocks[0] if is_single else blocks
