import os
import msgpack
from lazyimport import sqlitedict

class _SqliteDict(sqlitedict.SqliteDict):
    _fallbacks = None
    def __init__(self, filename, initial=None, **kw):
        self._fallbacks = {}
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, **kw)
        if initial:
            for k, v in initial.items():
                self.setdefault(k, v)

    def __repr__(self):
        return 'State({})'.format(dict(self))

    def fallbacks(self, **kw):
        '''Default values that are NOT persisted to disk (like setdefault does).
        These only exist for the lifespan of the script.
        '''
        self._fallbacks.update(kw)

    def __getitem__(self, k):
        try:
            return super().__getitem__(k)
        except KeyError:
            if k in self._fallbacks:
                return self._fallbacks[k]
            raise


def _proxy_method(*attrs):
    attrs = [a for at in attrs for a in at.split('.')]
    def inner(self, *a, **kw):
        obj = self
        for a in attrs:
            obj = getattr(obj, a)
        return obj(*a, **kw)
    inner.__name__ = attrs[-1]
    return inner


class State:
    db = None
    def __init__(self, filename, *a, **kw):
        self.db = _SqliteDict(
            filename, *a,
            encode=msgpack.packb,
            decode=msgpack.unpackb,
            autocommit=True, **kw)

    __setitem__ = _proxy_method('db.__setitem__')
    __len__ = _proxy_method('db.__len__')
    __nonzero__ = _proxy_method('db.__nonzero__')
    __iter__ = _proxy_method('db.__iter__')
    keys = _proxy_method('db.keys')
    values = _proxy_method('db.values')
    items = _proxy_method('db.items')
    setdefault = _proxy_method('db.setdefault')
    get = _proxy_method('db.get')
    pop = _proxy_method('db.pop')
    clear = _proxy_method('db.clear')
    fallbacks = _proxy_method('db.fallbacks')

    def __repr__(self):
        return 'State({})'.format(dict(self.db))

    def __getitem__(self, k):
        return as_updateable(self.db[k], self.db, k)

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        if k not in self.__class__.__dict__:
            self.db[k] = v
        else:
            super().__setattr__(k, v)

    def __delattr__(self, k):
        if k not in self.__class__.__dict__:
            try:
                del self.db[k]
            except KeyError:
                raise AttributeError(k)
        return super().__delattr__(k)

    def _check_merge(self, k, v):
        if isinstance(v, dict) and not v.pop('__overwrite', False):
            v = dict(self.db[k], **v)
        return v

    def updatekey(self, k, v=None, **kw):
        self.db[k] = self._check_merge(k, dict(v or {}, **kw))

    def update(self, dct, **kw):
        return self.db.update({
            k: self._check_merge(k, v)
            for k, v in dict(dct, kw).items()
        })



import functools
def _update_after(func):
    @functools.wraps(func)
    def inner(self, *a, **kw):
        _ = func(self, *a, **kw)
        self._db[self._key] = self
        return _
    return inner

# def _castupdateable(func):
#     @functools.wraps(func)
#     def inner(self, *a, **kw):
#         return as_updateable(func(self, *a, **kw), self._db, self._key)
#     return inner

class UpdateDict(dict):
    def __init__(self, value, db, key, **kw):
        super().__init__(value, **kw)
        self._db = db
        self._key = key

    __setitem__ = _update_after(dict.__setitem__)
    __delitem__ = _update_after(dict.__delitem__)
    update = _update_after(dict.update)
    setdefault = _update_after(dict.setdefault)
    clear = _update_after(dict.clear)


class UpdateList(list):
    def __init__(self, value, db, key, **kw):
        super().__init__(value, **kw)
        self._db = db
        self._key = key

    # __getitem__ = _castupdateable(list.__getitem__)
    __setitem__ = _update_after(list.__setitem__)
    __delitem__ = _update_after(list.__delitem__)
    append = _update_after(list.append)
    pop = _update_after(list.pop)
    remove = _update_after(list.remove)
    clear = _update_after(list.clear)


def as_updateable(x, db, key):
    if isinstance(x, dict):
        return UpdateDict(x, db, key)
    if isinstance(x, list):
        return UpdateList(x, db, key)
    return x
