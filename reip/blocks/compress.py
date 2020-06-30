import os
from lazyimport import tarfile
from .block import Block
import reip


class tar(Block):
    '''Write file to tar file.'''
    mode = 'r:'
    def __init__(self, filename, **kw):
        self.filename = filename
        super().__init__(**kw)

    def transform(self, input_fnames, meta):
        filename = self.filename
        with tarfile.open(filename, self.mode) as tf:
            for f in reip.utils.as_list(input_fnames):
                tf.add(f, arcname=os.path.basename(f))
        return filename


class gz(tar):
    '''Write file to tar.gz file.'''
    mode = 'r:gz'


tar.gz = gz
