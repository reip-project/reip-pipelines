from ..interface import Source
from reip.util import text


class Customer(Source):
    '''A Source object to read from a :py:class:`reip.stores.producer.Producer`
    '''
    def __init__(self, source, index, store_id, **kw):
        self.source = source
        self.id = index
        self.store_id = store_id
        super().__init__(**kw)

    def __str__(self):
        return '<{}[{}] queued={} {} of \n{}>'.format(
            self.__class__.__name__, self.id, len(self),
            self.source.readers[self.id],
            text.indent(self.source))

    def __len__(self):
        return self.source.head.counter - self.cursor.counter

    def next(self):
        '''Increment this cursor.'''
        if len(self):
            self.cursor.counter += 1

    def _get(self):
        return self.store.get(self.cursor.pos)

    @property
    def cursor(self):
        '''This customer's reader cursor. It marks the index
        of the data within the Producer's Store.'''
        return self.source.readers[self.id]

    @property
    def store(self):
        '''Links to the corresponding store from the Producer.
        This will vary depending on the configuration across
        Tasks.
        '''
        return self.source.stores[self.store_id]
