import json
import reip
import numpy as np
import csv
import json


class CsvWriter(reip.Block):
    _fname = _file = _writer = None

    def __init__(self, filename, fmt=one, max_rows=16384, **kw):
        self.filename = filename
        self.fmt = fmt
        self.fps = 20
        self.csv_file = None
        self.id = 0
        self.fnames = []
        super().__init__(**kw)

    def create_file(self, fname):
        self.csv_file = open(fname, "w")

    def write(self, X):
        writer = csv.DictWriter(self.csv_file, fieldnames=self.fmt)
        writer.writeheader()
        for data in X:
            row = {}
            for i in range(len(self.fmt)):
                row[self.fmt[i]] = data[i]
            writer.writerow(row)

    def write_by_frame(self, X, columns, frame=None):
        fname = self.filename.format(frame="{:04d}".format(int(self.id)))  # self.id/frame
        self.id += 1
        self.create_file(fname)
        self.fnames.append(fname)
        x_frame = np.array(X)[:, columns].tolist()
        self.write(x_frame)
        self.csv_file.close()

    def process(self, data, meta):
        assert (meta["data_type"] == "format"), "Invalid packet"
        allcolumns = meta["features"]
        fidx = allcolumns.index("frame_id")
        fid = data[0][fidx]
        selcolumns = [allcolumns.index(col) for col in self.fmt]
        self.write_by_frame(data, selcolumns)
        meta = {
            "sr": self.fps,
            "data_type": "csv",
            "format": self.fmt,
            # "frame_id": fid,
        }
        return [self.fnames], meta

    def finish(self):
        if self.csv_file is not None:
            self.csv_file.close()


class CsvReader(reip.Block):
    _fname = _file = _writer = None

    def __init__(self, filename, fmt=None, max_rows=16384, **kw):
        self.filename = filename
        # self.fmt = fmt
        self.fps = 20
        self.csv_file = None
        super().__init__(**kw)

    def create_file(self, fname):
        self.csv_file = open(fname, "rb")

    def read(self, fname):
        reader = csv.reader(fname, delimiter=",")
        next(reader)
        data_f = []
        for row in reader:
            data_f.append(row)
        return data_f

    def read_by_frame(self, fnames):
        data = []
        for fname in fnames:
            self.create_file(fname)
            data_f = self.read(fname)
            data.append(data_f)
            self.csv_file.close()
        return data

    def process(self, fnames, meta):
        assert (meta["data_type"] == "csv"), "Invalid packet"
        data = self.read_by_frame(fnames)

        meta = {
            "sr": self.fps,
            "data_type": "csv",
            "format": meta["format"],
            "frame_id": meta["frame_id"],
        }
        return [data], meta

    def finish(self):
        if self.csv_file is not None:
            self.csv_file.close()