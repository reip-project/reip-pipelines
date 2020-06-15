from .block import Block




class Echo(Block):
    def transform(self, **kw):
        print(', '.join('{}: {}'.format(k, v) for k, v in kw.items()))
        return kw
