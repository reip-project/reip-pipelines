import os
import tarfile

import reip


class TarGz(reip.Block):
    def __init__(self, filename='{time}.tar.gz', **kw):
        self.filename = filename
        super().__init__(**kw)

    def process(self, *files, meta):
        # get filename
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # write to tar
        with tarfile.open(fname, "w:gz") as tar:
            for f in files:
                tar.add(f, arcname=os.path.basename(f))
        return [fname], {}
