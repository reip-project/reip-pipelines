import os
from collections import deque
import csv
import reip
import numpy as np


class Csv(reip.Block):
    _fname = _file = _writer = None
    def __init__(self, filename='{time}.csv', headers=None, max_rows=1000, **kw):
        self.filename = filename
        self.max_rows = max_rows
        self.headers = headers
        self.n_rows = 0
        self._closed_files = deque()
        super().__init__(**kw)

    def should_get_new_writer(self, meta):
        return self.max_rows and self.n_rows >= self.max_rows

    def _new_writer(self, meta):
        if self._writer is not None:
            self._close_writer()
        # get filename
        fname = self.filename.format(**meta)
        reip.util.ensure_dir(fname)
        # make writer
        self._fname = fname
        self._file = open(fname, 'w', newline='')
        self._writer = csv.writer(self._file, **self.extra_kw)
        self.n_rows = 0
        if self.headers:
            self._writer.writerow(self.headers)
        return self._writer

    def _close_writer(self):
        if self._file is not None:
            self._file.close()
        if self._fname:
            self._closed_files.append(self._fname)
        return self._fname

    def _check_writer(self, meta):
        if self.should_get_new_writer(meta):
            self._new_writer(meta)
        return self._writer


    def init(self):
        pass

    def process(self, X, meta):
        writer = self._writer or self._new_writer(meta)

        for x in np.atleast_2d(X):
            writer.writerow(list(x))
            self.n_rows += 1
            writer = self._check_writer(meta)

        # print(self, X.shape, self.n_rows)
        if self._closed_files:
            return [self._closed_files.popleft()], {}

    def finish(self):
        self._close_writer()
