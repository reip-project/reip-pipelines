import csv
import reip
import numpy as np


class _CsvWriter(reip.util.CycledWriter):
    _file = None
    def __init__(self, filename, headers=None, max_rows=60, **kw):
        self.headers = headers
        self._kw = kw
        super().__init__(filename, file_length=max_rows)

    def _new_writer(self, fname, meta):
        self._file = open(fname, 'w', newline='')

        writer = csv.writer(self._file, **self._kw)
        if self.headers:
            writer.writerow(self.headers)
        return writer

    def _close_writer(self):
        if self._file is not None:
            self._file.close()

class Csv(reip.Block):
    '''A CSV writer.'''
    _fname = _file = _writer = None
    def __init__(self, filename='{time}.csv', headers=None, max_rows=1000, **kw):
        self.writer = _CsvWriter(filename, headers=headers, max_rows=max_rows)
        super().__init__(**kw)

    def process(self, X, meta):
        for x in np.atleast_2d(X):
            writer = self.writer.get(meta)
            writer.writerow(list(x))
            self.writer.increment(1)
        self.writer.get(meta)
        return self.writer.output_closed_file()

    def finish(self):
        self.writer.close()
