import os
import csv
import reip


class Csv(reip.Block):
    _fname = _file = _writer = None
    def __init__(self, filename='{time}.csv', max_rows=1000, **kw):
        self.filename = filename
        self.max_rows = max_rows
        self.n_rows = 0
        self.kw = kw
        super().__init__()

    def should_get_new_writer(self, meta):
        return self.max_rows and self.n_rows > self.max_rows

    def get_writer(self, meta):
        closed_file = None
        if self._writer is None or self.should_get_new_writer(meta):
            closed_file = self.close_writer()
            # get filename
            fname = self.filename.format(**meta)
            os.makedirs(os.path.dirname(fname), exist_ok=True)
            print('opening new csv writer:', fname)
            # make writer
            self._fname = fname
            self._file = open(fname, 'w', newline='')
            self._writer = csv.writer(self._file, **self.kw)
            self.n_rows = 0
        return self._writer, closed_file

    def close_writer(self):
        if self._file is not None:
            self._file.close()
        return self._fname

    def process(self, X, meta):
        writer, closed_file = self.get_writer(meta)
        # print(self, X, self.max_rows, self.n_rows, closed_file)
        for x in X:
            writer.writerow(list(x))
            self.n_rows += 1
        # print(self, X.shape, self.n_rows)
        if closed_file:
            return [closed_file], {}

    def finish(self):
        self.close_writer()
