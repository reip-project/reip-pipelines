'''Constants that can be used as sentinel values inside blocks.

'''

# this is arbitrary, just something that someone wouldn't realistically want
# to use as a value.
# normally, I'd use `object()`, but that won't work with `x is TOKEN` if it
# gets pickled.
make_token = lambda x: f'|(((( reip {x.upper()} ))))|'

# __SPLIT = '@#$%^&*()'
# _TOKEN_START, _TOKEN_END = make_token(__SPLIT).split(__SPLIT)
# is_token = lambda x: isinstance(x, str) and x.startswith(_TOKEN_START) and x.endswith(_TOKEN_END)

class Token:
    def __init__(self, name):
        self.name = name.upper()
        self.id = make_token(name)

    def __repr__(self):
        return self.id

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.check(other)

    def check(self, other):
        return isinstance(other, Token) and self.id == other.id


UNSET = Token('UNSET')
# Use this to signify a blank output. If you have a block that outputs
# [0, 1, BLANK, 2, 3], the next block would receive process(1, 2, 3, 4)
BLANK = Token('BLANK')
# return this from a block and the sources won't be incremented.
RETRY = Token('RETRY')
NEXT = Token('NEXT')
# if a block returns these, it will close/terminate itself and will
# cascade down to other blocks.
CLOSE = Token('CLOSE')
TERMINATE = Token('TERMINATE')

SOURCE_TOKENS = {RETRY, NEXT}

MIN_SLEEP = 1e-6
