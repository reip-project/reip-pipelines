'''Data Serializers

TODO:
 - how should we store data vs metadata ?

'''
from lazyimport import json as json_
from .block import Block



class csv(Block):
    pass


class json(Block):
    def __init__(self, filename=None, **kw):
        self.filename = filename
        super().__init__(**kw)

    def transform(self, data, meta):
        fname = self.filename
        d = {'data': data, 'meta': meta}

        if not fname:
            return json_.dumps(d)
        json_.dump(fname, d)
        return fname


class yaml(Block):
    pass


class pickle(Block):
    pass


class msgpack(Block):
    pass
