import multiprocessing as mp
import multiprocessing.queues as mpq
from multiprocessing import context

SERIALIZERS = {}


class Pickler(context.reduction.ForkingPickler):
    protocol = -1
    def __init__(self, file, protocol=..., **kw):
        super().__init__(file, self.protocol if protocol == ... else protocol, **kw)

class Pickler5(Pickler):
    protocol = 5
class Pickler4(Pickler):
    protocol = 4
class Pickler3(Pickler):
    protocol = 3

def get_serializer(name):
    '''Returns an object with a loads and dumps member.'''
    if name == 'pickle':
        return Pickler
    if name == 'pickle5':
        return Pickler5
    if name == 'pickle4':
        return Pickler4
    if name == 'pickle3':
        return Pickler3
    if name == 'json':
        import json
        return json
    if name == 'ujson':
        import ujson
        return ujson
    if name == 'msgpack':
        import msgpack
        return msgpack
    if name in SERIALIZERS:
        return SERIALIZERS[name]
    if isinstance(name, str):
        raise ValueError('Serializer "{}" could not be found.'.format(name))
    return name

def register_serializer(cls, name=None):
    SERIALIZERS[name or cls.__name__] = cls


class _BytesQueue(mpq.SimpleQueue):
    def __init__(self, ctx=None):
        super().__init__(ctx=mp.get_context() if ctx is None else ctx)

    def get(self):
        with self._rlock:
            return self._reader.recv_bytes()

    def put(self, obj):
        if self._wlock is None:  # writes to win32 pipe are atomic
            self._writer.send_bytes(obj)
        else:
            with self._wlock:
                self._writer.send_bytes(obj)


class Queue(_BytesQueue):
    serializer = 'pickle'
    def __init__(self, serializer=None, **kw):
        self.serializer = get_serializer(serializer or self.serializer)
        super().__init__(**kw)

    def get(self):
        return self.serializer.loads(super().get())

    def put(self, obj):
        return super().put(self.serializer.dumps(obj))
