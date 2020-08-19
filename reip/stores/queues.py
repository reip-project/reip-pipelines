import pyarrow as pa
import multiprocessing as mp
import multiprocessing.queues


class FasterSimpleQueue(mp.queues.SimpleQueue):
    def __init__(self, ctx=None):
        super().__init__(ctx=mp.get_context() if ctx is None else ctx)

    def _dumps(self, obj):
        # return _ForkingPickler.dumps(obj)
        return pa.serialize(obj).to_buffer()

    def _loads(self, obj):
        # return _ForkingPickler.loads(res)
        return pa.deserialize(obj)

    def get(self):
        with self._rlock:
            res = self._reader.recv_bytes()
        return self._loads(res)

    def put(self, obj):
        obj = self._dumps(obj)
        if self._wlock is None:  # writes to win32 pipe are atomic
            self._writer.send_bytes(obj)
        else:
            with self._wlock:
                self._writer.send_bytes(obj)
