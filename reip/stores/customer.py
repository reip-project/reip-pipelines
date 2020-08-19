from ..interface import Source
from reip.util import text


class Customer(Source):
    def __init__(self, source, index, store_id, **kw):
        self.source = source
        self.id = index
        self.store_id = store_id
        super().__init__(**kw)

    def __str__(self):
        return '<{}[{}] {} of \n{}>'.format(
            self.__class__.__name__, self.id, self.source.readers[self.id],
            text.indent(self.source))

    @property
    def cursor(self):
        return self.source.readers[self.id]

    @property
    def store(self):
        return self.source.stores[self.store_id]

    def empty(self):
        return self.source.head.counter == self.cursor.counter

    def last(self):
        return (self.source.head.counter - self.cursor.counter) <= 1

    def next(self):
        self.cursor.counter += 1

    def _get(self):
        return self.store.get(self.cursor.pos)
