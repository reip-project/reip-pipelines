'''Simple block implementations.



'''

from .block import Block




class echo(Block):
    '''Print out the data.'''
    def __init__(self, message, **kw):
        super().__init__(**kw)
        self.message = message

    def transform(self, X, meta):
        print(f'''
- {self.message} -----
    Data: shape={X.shape}, dtype={X.dtype}
    Metadata: {meta}
----------------------'''.strip())
        return X, meta
