'''

Outstanding issues:
 - Every loop iteration must yield something otherwise it will hang
    - we may need asyncio for this kind of block :/
    - is there any way to

'''
import sys
import functools
from contextlib import contextmanager
import reip


class Streamer(reip.Block):
    _stream = _block = None
    def __init__(self, new, *a, name=None, **kw):
        self._new_block = new
        self._extra_args = a
        self.__class__ = type(new.__name__, (self.__class__,), {})
        super().__init__(name=name, extra_kw=True, **kw)

    def init(self):
        self._feeder = _feeder()
        next(self._feeder)  # clear initial value
        self._block = self._new_block(
            self._feeder, *self._extra_args, **self.extra_kw)

    def process(self, *xs, meta):
        # still assumes 1-to-1
        self._feeder.send(*xs, meta)
        return next(self._block)

    def finish(self):
        # run to completion and discard anything additional
        # QUESTION: should we catch exceptions here?
        # print('FINISHING', self, list(self._block))
        # for _ in self._block:
        #     pass
        self._block.close()


def _feeder(value=None):
    while True:
        value = yield value


def streamer(func=None):
    @functools.wraps(func)
    def outer(*a, **kw):
        return Streamer(func, *a, **kw)
    return outer


class _ProcessFunctionBlock(reip.Block):
    _BLOCK_INIT_ARGS = {}
    def __init__(self, *a, **kw):
        super().__init__(*a, **self._BLOCK_INIT_ARGS, **kw)

@reip.util.decorator
def process_func(func, **kw):
    return type(func.__name__, (_ProcessFunctionBlock,), {
        'process': func, '_BLOCK_INIT_ARGS': kw
    })


class _ContextFunc(reip.Block):
    _context = _process = None
    def __init__(self, func, **kw):
        self.func = contextmanager(func)
        super().__init__(extra_kw=True, **kw)

    def init(self):
        self._context = self.func(**self.extra_kw)
        self._process = self._context.__enter__()

    def process(self, *xs, meta):
        return self._process(*xs, meta)

    def finish(self):
        self._context.__exit__(*sys.exc_info())

def context_func(func=None):
    @functools.wraps(func)
    def outer(*a, **kw):
        return _ContextFunc(func, *a, **kw)
    return outer


# __name__ = '__main__'
if __name__ == '__main__':
    import reip.blocks as B

    @streamer
    def custom_block(stream=..., step=2):  # the ... is just to shut up pylint.
        try:
            # basically init() - do some initialization
            start = 10
            # basically process() - do some processing
            for i, ((data,), meta) in enumerate(stream, start):
                yield [data * step], {'index': i}
        finally:
            # basically finish() - do some cleanup
            print(f'\n\n!!!!!!!!!! all done. just cleaning up {stream}. !!!!!!!\n\n')


    (B.Interval(1)
     .to(B.Increment())
     .to(custom_block(step=4))  # no stream parameter was making pylint freak out
     .to(B.Debug('asdf')))
    reip.run(duration=6)

    @ContextFunc
    def block():
        try:
            ... # do_init()
            def process(x, meta):
                return [x], {}
            yield process
        finally:
            ... # do_finish()
