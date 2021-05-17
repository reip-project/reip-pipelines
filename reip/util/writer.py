import collections
import reip
# import time


class CycledWriter:
    '''Get rid of the boilerplate needed to

    '''
    _fname = None
    _writer = None
    def __init__(self, filename, file_length=60):
        self.filename = str(filename)
        self.file_length = file_length
        assert self.file_length is None or self.file_length > 0
        self.frame_index = 0
        self._closed_files = collections.deque()

    def get(self, meta):
        if self._writer is None or self._should_cycle(meta):
            self._writer = self._get_new_writer(meta)
        return self._writer

    def increment(self, n=1):
        self.frame_index += n

    def output_closed_file(self, meta=None):
        if self._closed_files:
            return [self._closed_files.popleft()], meta or {}

    def close(self):
        if self._writer is not None:
            self._close_writer()
        if self._fname:
            self._closed_files.append(self._fname)
        return self._fname

    def _should_cycle(self, meta):
        return self.file_length and self.frame_index >= self.file_length

    def _get_new_writer(self, meta):
        self.close()
        # get filename
        # meta["time"] = time.time()
        self._fname = fname = self.filename.format(**meta)
        reip.util.ensure_dir(fname)
        # make writer
        self.frame_index = 0
        return self._new_writer(fname, meta)

    def _new_writer(self, fname, meta):
        raise NotImplementedError

    def _close_writer(self):
        raise NotImplementedError
