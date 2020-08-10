from .pointers import Pointer


class BaseStore:
    Pointer = Pointer

    def __str__(self):
        return '<{} n={}>'.format(self.__class__.__name__, len(self))

    def __len__(self):
        raise NotImplementedError

    def put(self, data, meta=None, id=None):
        raise NotImplementedError

    def get(self, id):
        raise NotImplementedError

    def delete(self, ids):
        raise NotImplementedError
