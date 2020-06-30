'''Operating system operations.


'''

import os
import glob as glob_
from .block import Block



class glob(Block):
    '''List files.'''
    def __init__(self, pattern, **kw):
        self.pattern = pattern
        super().__init__(**kw)

    def transform(self, X, meta):
        return glob_.glob(self.pattern)



class rm(Block):
    '''Remove files fed to input.'''

    def transform(self, files, meta):
        for f in files:
            os.remove(f)
        return files
