import os
from functools import wraps
import numpy as np



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
    )[:length]


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


def resolve_call(func, *a, **kw):
    return func(*a, **kw) if callable(func) else func


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
    '''Get file name. e.g. path/to/fileA.txt => fileA.'''
    return os.path.splitext(os.path.basename(file))[0]


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
    return hasattr(iterable,'__iter__') and not hasattr(iterable,'__len__')

def as_iterlike(x):
    return (
        x if isinstance(x, (list, tuple, np.ndarray)) or is_iter(x) else [x])

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


def flatten(X):
    if isinstance(X, (list, tuple)):
        yield from (x for xs in X for x in flatten(xs))
    else:
        yield X

# class MpValueProp:
#     def __init__(self, name):
#         self.name = name
#
#     def __get__(self, instance, owner=None):
#         return getattr(instance, self.name).value
#
#     def __set__(self, instance, value):
#         getattr(instance, self.name).value = value
