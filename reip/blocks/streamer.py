'''

Outstanding issues:
 - Every loop iteration must yield something otherwise it will hang
    - we may need asyncio for this kind of block :/
    - is there any way to

'''
import reip


class Streamer(reip.Block):
    _stream = _block = None
    def __init__(self, new, name=None, **kw):
        self._new_block = new
        self.__class__ = type(new.__name__, (self.__class__,), {})
        super().__init__(name=name, **kw)

    def _init_stream(self):
        stream = super()._init_stream()
        self._block = self._new_block(stream, **self.extra_kw)
        return self._block  # self._sw.iter(self._block, 'process')

    def finish(self):
        # run to completion and discard anything additional
        # QUESTION: should we catch exceptions here?
        print('FINISHING', self, list(self._block))
        for _ in self._block:
            pass


def streamer(func=None):
    def outer(**kw):
        return Streamer(func, **kw)
    return outer


# __name__ = '__main__'
if __name__ == '__main__':
    import reip
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

    reip.Graph.default
    reip.run(duration=6)
