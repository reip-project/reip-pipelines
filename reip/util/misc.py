import os
import re
import time
import contextlib
from functools import wraps
import numpy as np

def always(*a, **kw):
    return True

def never(*a, **kw):
    return False

def min_rate(rate, strategy=all, fail_rate=None, fail_count=1):
    '''A source strategy for blocks that will fire once every x seconds even if there's no inputs.
    Useful to handle null cases and prevent hanging.
    
    Arguments:
        rate (float): the minimum time in seconds to wait.
        strategy (callable): the source strategy to use.
        fail_count (int): the number of times for the source 
            strategy to fail before switching from rate to 
            fail_rate.
        fail_rate (float): the minimum time in seconds to wait
            after `strategy` has failed `fail_count` times.
            This lets you give more tolerance when a block isn't outputting,
            but don't want to hold up downstream blocks if a previous 
            block isn't firing.
    '''
    fail_rate = fail_rate or rate
    def func(*a, **kw):
        dt = time.time() - (func.t_last or time.time())
        func.t_last += dt
        
        # check if it passed
        passed = strategy(*a, **kw)
        if passed:
           func.fail_count = 0
           return True

        # otherwise check if we're over the min rate
        func.fail_count += 1
        rate_ = fail_rate if fail_count and func.fail_count > fail_count else rate
        return dt >= rate_
    func.t_last = 0
    func.fail_count = 0

    def clear():
        func.t_last = 0
    func.clear = clear
    return func


def resize_list(lst, length, value=None):
    '''Resize a list to be a specific length.

    Example:
    >>> x = [1, 2]
    >>> assert resize_list(x, 5) == [1, 2, None, None, None]
    >>> assert resize_list(x, 5, 10) == [1, 2, 10, 10, 10]
    >>> assert resize_list(x, 4, lambda: x[0]) == [1, 2, 1, 1]  # some callable
    '''
    return (
        lst + [
            value() if callable(value) else value
            for i in range(max(0, length - len(lst)))
        ]
    )[:length] if length is not None and len(lst) != length else lst


def decorator(__func__=None, **kw):
    '''A convenience wrapper that allows you to define a decorator with optional
    initialization parameters.

    Example:
    >>> def my_decorator(func, **kw):
    ...     @functools.wraps(func)
    ...     def inner(*a, **kwi):
    ...         return func(*a, **dict(kw, **kw))
    ...     return inner
    >>> @my_decorator
    ... def asdf(x=10, y=15):
    ...     return x+y
    >>> @my_decorator(y=20)
    ... def asdf2(x=10, y=15):
    ...     return x+y
    >>> assert asdf() == 25 and asdf2() == 30
    '''
    def decorated(func):
        @wraps(func)
        def inner(*a, **kwi):
            return func(*a, **dict(kw, **kwi))
        return inner
    return decorated(__func__) if callable(__func__) else decorated


def partial(__partial_func__, *a, __name__=None, **kw):
    @wraps(__partial_func__)
    def inner(*ai, **kwi):
        return __partial_func__(*a, *ai, **dict(kw, **kwi))
    if __name__ is not None:
        inner.__name__ = __name__
    return inner

def create_partial(__partial_func__, *a, __name__=None, **kw):
    return partial(partial, __partial_func__, *a, __name__=__name__ or __partial_func__.__name__, **kw)


def resolve_call(func, *a, **kw):
    return func(*a, **kw) if callable(func) else func

def as_func(func):
    return func if callable(func) else (lambda: func)


def ensure_dir(fname):
    '''Make sure that the directory that this filename is in exists. Does nothing
    if this file is in the current working directory.'''
    parent = os.path.dirname(fname)
    if parent:  # ignore if parent is cwd
        os.makedirs(parent, exist_ok=True)
    return fname


def adjacent_file(file, *f):
    return os.path.abspath(os.path.join(os.path.dirname(file), *f))


def fname(file):
    '''Get file name. e.g. path/to/fileA.txt => fileA'''
    return os.path.splitext(os.path.basename(file))[0]


def fwrite(fname, *lines, mode='w'):
    '''write to file.'''
    d = os.path.dirname(fname)
    if d and not os.path.exists(d):
        os.makedirs(d)
    with open(os.path.expanduser(fname), mode) as f:
        f.write('\n'.join(map(str, lines)))


def as_list(x):
    '''Convert or wrap value as a list.

    Examples:
    >>> assert as_list(5) == [5]
    >>> assert as_list('asdf') == ['asdf']
    >>> assert as_list((1, 2)) == [1, 2]
    >>> assert as_list([1, 2]) == [1, 2]
    '''
    return (
        x if isinstance(x, list)
        else list(x) if isinstance(x, tuple)
        else [x])

def is_iter(iterable):
    return not hasattr(iterable,'__len__') and hasattr(iterable,'__iter__')

def as_iterlike(x, like=(list, tuple, set, np.ndarray)):
    return x if isinstance(x, like) or is_iter(x) else [x]

def squeeze(x):
    '''If the input is a one-element list or tuple, take the first element.
    (removes an unnecessary container.)

    Examples:
    >>> assert squeeze([5]) == 5
    >>> assert squeeze((1,)) == 1
    >>> assert squeeze([1, 2]) == [1, 2]
    >>> assert squeeze('asdf') == 'asdf'
    >>> assert squeeze(('asdf',)) == 'asdf'
    >>> assert squeeze((1, 2)) == (1, 2)
    '''
    return x[0] if isinstance(x, (list, tuple)) and len(x) == 1 else x

def notnone(x):
    return x is not None

def filter_none(xs):
    return [x for x in xs if x is not None]


def separate(xs, *conditions, keep_fails=True):
    conditions = conditions or ((lambda x: x is not None),)
    outs = [[] for i in range(len(conditions)+1)]
    for x in xs:
        for i, c in enumerate(conditions):
            if c(x):
                outs[i].append(x)
                break
        else:
            outs[-1].append(x)
    return outs


def flatten(X, args=(), call=False, **kw):
    if isinstance(X, (list, tuple)):
        yield from (x for xs in X for x in flatten(xs, call=call, args=args, **kw))
    elif call and callable(X):
        yield from flatten(X(*args, **kw), call=call, args=args, **kw)
    else:
        yield X


def mergedict(*dicts, args=(), call=True, **kw):
    return _merge(flatten(dicts, args=args, call=call, **kw), call=call)

def _merge(flat, call=True):
    out = {}
    for d in flat:
        if not d:
            continue
        if not call and callable(d):
            return ([out] if out else []) + [d] + as_list(_merge(flat, call=call))
        out.update(d)
    return out


def matchmany(text, *patterns):
    return {
        k: v for m in (re.search(p, text) for p in patterns) if m
        for k, v in m.groupdict().items()}


@contextlib.contextmanager
def multicontext(*items):
    '''Use a variable set of context managers as one.'''
    with contextlib.ExitStack() as stack:
        yield [stack.enter_context(x) for x in items]




# @wraps(mergedict)
# def _mergedicts(dicts, *a, **kw):
#     out = {}
#     for d in flatten(dicts, *a, call=True, **kw):
#         out.update(d)
#     return out


# >     1d:  1d02h05m
# >    1hr:  1h03m04s
# > 10mins:  11m05s
# >  2mins:   2m05s
#         : 90.065s
#         :  2.065s

_TIME_BREAKS = [
    (60 * 60 * 24 * 7, '{w:.0f}w:{d:.0f}d:{h:.0f}h'.format),
    (60 * 60 * 24,     '{d:.0f}d:{h:.0f}h:{m:.0f}m'.format),
    (60 * 60,          '{h:.0f}h:{m:.0f}m:{s:.0f}s'.format),
    (60 * 10,          '{m:.0f}m:{s:.0f}s'.format),
    (60 * 1,           '{m:.0f}m:{s:.1f}s'.format),
    (0,                '{s:.3f}s'.format),
]

def _factor_time(t):
    wks, days = divmod(t, 60*60*24*7)
    days, hrs = divmod(t, 60*60*24)
    hrs, mins = divmod(hrs, 60*60)
    mins, secs = divmod(mins, 60)
    return {'w': wks, 'd': days, 'h': hrs, 'm': mins, 's': secs}

def human_time(secs):
    suffix = ' ago' if secs < 0 else ''
    secs = abs(secs)
    return '({}{})'.format(next((
        fmt(**_factor_time(secs))
        for t, fmt in _TIME_BREAKS if secs >= t
    )), suffix)


# class MpValueProp:
#     def __init__(self, name):
#         self.name = name
#
#     def __get__(self, instance, owner=None):
#         return getattr(instance, self.name).value
#
#     def __set__(self, instance, value):
#         getattr(instance, self.name).value = value
