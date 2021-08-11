import os
import reip


class CSVWriter(reip.Block):
    def __init__(self, filename, n_rows=60, max_rate=1, **kw):
        self.filename_pattern = filename
        self.n_rows = n_rows
        super().__init__(max_rate=max_rate, **kw)

    def _new(self):
        self.filename = self.filename_pattern.format(strftime("%Y_%m_%d-%H_%M_%S"))
        self.count = 0

    def init(self):
        self._new()

    def process(self, X, meta):
        if self.count >= self.n_rows:
            self._new()

        with open(self.filename, 'a') as fd:
            writer = csv.writer(fd)
            if not self.count:
                writer.writerow(self.header)
            writer.writerow(data)
        self.count += 1