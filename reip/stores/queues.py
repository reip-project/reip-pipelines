import pyarrow as pa
import multiprocessing as mp


class FasterSimpleQueue(mp.queues.SimpleQueue):
    def get(self):
        with self._rlock:
            res = self._reader.recv_bytes()
        # unserialize the data after having released the lock
        # return _ForkingPickler.loads(res)
        return pa.deserialize(res)

    def put(self, obj):
        # serialize the data before acquiring the lock
        # obj = _ForkingPickler.dumps(obj)
        obj = pa.serialize(obj).to_buffer()
        if self._wlock is None:
            # writes to a message oriented win32 pipe are atomic
            self._writer.send_bytes(obj)
        else:
            with self._wlock:
                self._writer.send_bytes(obj)
