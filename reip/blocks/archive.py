import io
import os
import glob
import tarfile

import reip


class Tar(reip.Block):
    def __init__(self, filename='{time}.tar', remove_files=False, extra_files=None, gz=None, **kw):
        '''Store files in a .tar/.targz file.
        
        Arguments:
            ...
            extra_files (callable): Should return a dictionary {filename: bytes} that represent
                additional files to add to the archive. A common use of this is to write 
                metadata as json to file so that it persists reboots.
                If the value is a string that points to an existing file, that file will 
                be read as bytes. Otherwise, strings will be encoded as utf-8.
        '''
        self.filename = filename
        self.remove_files = remove_files
        self.gz = filename.endswith('.gz') if gz is None else gz
        self.extra_files = extra_files
        super().__init__(n_inputs=None, **kw)

    def process(self, *files, meta):
        # get filename
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)

        extra_files = dict(self.extra_files(*files, meta=meta) or {}) if callable(self.extra_files) else {}
        # write to tar
        with tarfile.open(fname, "w:gz" if self.gz else 'w') as tar:
            for f in files:
                tar.add(f, arcname=os.path.basename(f))
            for f, data in extra_files.items():
                tar_addbytes(tar, f, data)
        if self.remove_files:
            for f in files:
                os.remove(f)
        return [fname], {}

TarGz = Tar


def tar_addbytes(tar, f, data):
    if not isinstance(data, bytes):
        if isinstance(data, str):
            if os.path.isfile(data):
                data = open(data, 'rb')
            else:
                data = data.encode('utf-8')

    if not hasattr(data, 'read'):
        data = io.BytesIO(data)

    t = tarfile.TarInfo(f)
    t.size = len(data)
    tar.addfile(t, data)

