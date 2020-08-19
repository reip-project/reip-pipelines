'''Constants that can be used as sentinel values inside blocks.

'''

# this is arbitrary, just something that someone wouldn't realistically want
# to use as a value.
# normally, I'd use `object()`, but that won't work with `x is TOKEN` if it
# gets pickled.
make_token = lambda x: f' |*!@@@{x.upper()}@@@!*| '

# return this from a block and the sources won't be incremented.
RETRY = make_token('RETRY')
CLOSE = make_token('CLOSE')
TERMINATE = make_token('TERMINATE')

MIN_SLEEP = 1e-6
