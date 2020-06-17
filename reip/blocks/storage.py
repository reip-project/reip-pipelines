from .block import Block


class CSVSink(Block):
    '''Write data to csv.'''
    name = 'csv'
    def __init__(self, *a, output_file=None, **kw):
        self.output_file = output_file
        super().__init__(*a, **kw)

    def _get_output_rows(self, kw):
        sizes = {1 if len(x.shape) == 1 else x.shape[0] for x in kw.values()}
        nrows = max(sizes)
        assert sizes < {nrows, 1}, 'unmatchable array sizes. Must be either {} or 1.'.format(nrows)
        rows = ([x.tolist()] * nrows if len(x.shape) == 1 else x.tolist() for x in kw.values())
        columns = self.input_block.output_names()
        columns = sum((columns[k] for k in kw.keys()), [])
        return columns, (dict(zip(columns, sum(row, []))) for row in zip(*rows))

    def action(self, **kw):
        import os
        import csv
        columns, rows = self._get_output_rows(kw)
        out_file = self.output_file
        file_exists = os.path.isfile(out_file)

        with open(out_file, 'w', newline='') as f:
            writer = csv.DictWriter(out_file, fieldnames=columns)
            if not file_exists:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return out_file
