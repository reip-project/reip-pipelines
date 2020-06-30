from .block import Block


class while_(Block):
    def __init__(self, check, items, **kw):
        super().__init__(**kw)
        self.check = check
        self.items = items

    def transform(self, X, meta):
        while self.check.run(X, meta): # ???
            self.items.run(X, meta)
        return X, meta
