import os
import tarfile
import time
import reip


class Tar(reip.Block):
    '''Archive files in a .tar file.'''
    def __init__(self, filename='{time}.tar', remove_files=False, gz=None, **kw):
        self.filename = filename
        self.remove_files = remove_files
        self.gz = filename.endswith('.gz') if gz is None else gz
        super().__init__(**kw)

    def process(self, *files, meta):
        # get filename
        meta["time"] = time.time()
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # write to tar
        with tarfile.open(fname, "w:gz" if self.gz else 'w') as tar:
            for f in files:
                tar.add(f, arcname=os.path.basename(f))
        if self.remove_files:
            for f in files:
                os.remove(f)
        return [fname], {}

class TarGz(Tar):
    def __init__(self, filename='{time}.tgz', **kw):
        super().__init__(filename, gz=True, **kw)
