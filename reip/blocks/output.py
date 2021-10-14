import os
import csv
import time
import collections
import reip
import numpy as np

class CsvWrite(reip.Block):
    '''
    spl_headers = ['l{}eq'.format(w) for w in 'ZAC']
    CsvWrite('spl/{time}.csv', lambda X, meta: [
        dict(zip(spl_headers, x), time='{:.3f}'.format(meta['time'])
        for x in X
    ])
    CsvWrite('emb/{time}.csv', asrow=lambda X, meta: [
        dict(enumerate(x), time='{:.3f}'.format(meta['time'])
        for x in X])
    '''
    def __init__(self, fname, asrow=None, headers=None, max_rows=None, len_secs=None, min_rows=1, discard_below_min=False, **kw):
        self.fname = str(fname)
        self.len_secs = len_secs
        self.min_rows = min_rows
        self.max_rows = max_rows
        self.discard_below_min = discard_below_min
        self.headers = headers
        self.asrow = asrow
        if not self.len_secs and not self.max_rows:
            self.len_secs = 60
        super().__init__(extra_kw=True, **kw)

    def init(self):
        self.q = collections.deque()
        self.start_time = time.time()
        self.idx = 0

    def finish(self):
        self.q = None

    def process(self, rows, meta):
        # preprocess rows
        rows = (
            reip.util.as_list(self.asrow(rows, meta)) 
            if callable(self.asrow) else [rows])
        for row in rows:
            self.q.append((row, meta))
            # write to file
            if self.should_write():
                self.t_last = time.time()
                rows, metas = zip(*self.q)
                fname = self.fname.format(**metas[0], metas=metas)
                write_csv(fname, rows, self.headers, **self.extra_kw)
                self.q.clear()
                yield fname, metas[0]

    def should_write(self):
        # write a new file every n rows
        if self.max_rows and len(self.q) >= self.max_rows:
            return True
        
        # write a new file every n seconds
        if self.len_secs:
            idx, secs = divmod(time.time() - self.start_time, self.len_secs)
            if idx > self.idx:
                self.idx = idx
                # make sure we have n rows in the file
                if self.min_rows and len(self.q) < self.min_rows:
                    if self.discard_below_min:
                        self.q.clear()
                    return False
                return True 
        return False


def write_csv(fname, data, *a, **kw):
    '''Write to a csv. Handles list of dicts and lists of lists.'''
    os.makedirs(os.path.dirname(fname) or '.', exist_ok=True)
    with open(fname, 'w') as fhandle:
        _write_csv(fhandle, data, *a, **kw)
    return fname

# def csv_str(data, *a, **kw):
#     import io
#     out = io.StringIO()
#     _write_csv(out, data, *a, **kw)
#     return out.getvalue()

import json
def _write_csv(fhandle, data, headers=None, decimals=None, n_peek=10):
    '''Write to a csv. Handles list of dicts and lists of lists.'''
    # get the first few rows
    firsts, data = _peek(data, n_peek)
    ncols = max((len(x) for x in firsts), default=0)
    # convert dict to row list
    if any(isinstance(d, dict) for d in firsts):
        headers = headers or sorted({k for d in firsts for k in d})
        data = ([row.get(k, '') for k in headers] for row in data)

    # get format args for each column
    args = [{} for i in range(ncols)]
    for kw, dec in zip(args, _expanded_arg(decimals, headers, ncols)):
        kw.update(decimals=dec)
    # write to csv
    writer = csv.writer(fhandle)
    if headers:
        writer.writerow(headers)
    for row in data:
        writer.writerow([_process_cell(x, **kw) for x, kw in zip(row, args)])


def _peek(it, n=1):
    '''Look at the first n elements of a csv.'''
    it = iter(it)
    first = [x for i, x in zip(range(n), it)]
    return first, (x for xs in (first, it) for x in xs)


def _process_cell(value, decimals=None):
    if isinstance(value, np.generic):
        value = value.item()
    elif isinstance(value, np.ndarray):
        value = value.tolist()

    if decimals is not None and isinstance(value, float):
        value = '{:.{dec}f}'.format(value, dec=decimals)
    return value


def _expanded_arg(arg, headers=None, ncols=None):
    ncols = len(headers) if ncols is None else ncols
    if arg is not None:
        if isinstance(arg, dict):
            if headers is None:
                raise ValueError('You specified a csv format option as a dict ({}), but there are no headers.'.format(arg))
            arg = [arg.get(h) for h in headers]
        if isinstance(arg, (list, tuple)):
            arg = list(arg) + [None]*(ncols - len(arg))
        else:
            arg = [arg]*ncols
    else:
        arg = [None]*ncols
    return arg