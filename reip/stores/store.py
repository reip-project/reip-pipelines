from .base import BaseStore


class Store(BaseStore):
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
