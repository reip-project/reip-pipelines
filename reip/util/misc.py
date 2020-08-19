import os


def ensure_dir(fname):
    '''Make sure that the directory that this filename is in exists. Does nothing
    if this file is in the current working directory.'''
    parent = os.path.dirname(fname)
    if parent:  # ignore if parent is cwd
        os.makedirs(parent, exist_ok=True)
    return fname


def adjacent_file(file, *f):
    return os.path.join(os.path.dirname(file), *f)


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


# class MpValueProp:
#     def __init__(self, name):
#         self.name = name
#
#     def __get__(self, instance, owner=None):
#         return getattr(instance, self.name).value
#
#     def __set__(self, instance, value):
#         getattr(instance, self.name).value = value
