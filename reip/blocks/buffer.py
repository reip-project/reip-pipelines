import queue
import numpy as np
import reip


class Rebuffer(reip.Block):
    def __init__(self, size=None, duration=None, sr_key='sr', **kw):
        assert size or duration, 'You must specify a size or duration.'
        self.size = size
        self.duration = duration
        self.sr_key = sr_key
        super().__init__(**kw)

    def init(self):
        self._q = queue.Queue()
        self.sr = None
        self.current_size = 0

    def process(self, x, meta):
        # calculate the size the first time using the sr in metadata
        if not self.size:
            self.sr = self.sr or meta[self.sr_key]
            self.size = self.duration * self.sr

        # place buffer into queue. If buffer is full, gather buffers and emit.
        if self._place_buffer(x, meta):
            return self._gather_buffers()

    def _place_buffer(self, x, meta):
        '''put items on the queue and return if the buffer is full.'''
        xsize = self._get_size(x)
        self.current_size += xsize
        self._q.put((x, meta, xsize))
        return self.current_size >= self.size

    def _gather_buffers(self):
        '''Read items from the queue and emit once it's reached full size.'''
        size = 0
        xs, metas = [], []
        while size < self.size:
            x, meta, xsize = self._q.get()
            xs.append(x)
            metas.append(meta)
            size += xsize
            self.current_size -= xsize
        return [self._merge_buffers(xs)], self._merge_meta(metas)

    def _get_size(self, buf):
        '''Return the size of a buffer, based on it's type.'''
        return len(buf)

    def _merge_buffers(self, bufs):
        return np.concatenate(bufs)

    def _merge_meta(self, metas):
        return metas[0]
