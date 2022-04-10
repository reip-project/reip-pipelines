from .base import BaseStore


class Store(BaseStore):
    '''A basic store that stores it's elements in a list.'''
    def __init__(self, size):
        self.items = [None] * size

    def __len__(self):
        return len(self.items)

    def put(self, data, meta=None, id=None):
        self.items[id] = data, meta

    def get(self, id):
        return self.items[id]

    def delete(self, ids):
        for i in ids:
            self.items[i] = None
