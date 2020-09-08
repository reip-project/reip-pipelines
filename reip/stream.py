import time
import reip
from reip.util import text, iters

class Stream:
    '''Multiplexing multiple sources together. Abstracts away the internals of
    a block so that they can be used outside of a threaded context.


    with reip.Graph() as g:
        block = B.Block()

    with g.run_scope():
        # open a stream and iterate over it.
        with block.output_stream(duration=5) as stream:
            for (data,), meta in stream:
                print(data, meta)

    '''
    _retry = False
    _delay = 1e-6
    should_wait = True
    running = True
    terminated = False
    signal = None
    def __init__(self, sources, loop=None, auto_next=True, timeout=None, name='', **kw):
        self.name = name or ''
        self.sources = sources
        self.loop = self.make_loop(**kw) if loop is None else loop
        self.auto_next = auto_next
        self.timeout = timeout

    def __str__(self):
        state = (
            ' '.join(('will-wait' * self.should_wait, 'terminated' * self.terminated))
            or 'running' if self.running else 'paused')

        srcs = ''.join(f'\n{s}' for s in self.sources)
        return f'<{self.__class__.__name__}({self.name}) {state} {text.indent(srcs)}>'

    def reset(self):
        self.signal = None
        self.resume()

    def __iter__(self):
        self.reset()
        t_last = time.time()
        for _ in self.loop:
            # if the stream is terminated, exit immediately
            if self.terminated:
                return
            # if the stream doesn't have any sources, then we can close
            if not self.sources and not self.should_wait:
                return
            # if the stream has a timeout set, return if we exceed that
            if self.timeout and time.time() - t_last >= self.timeout:
                return
            # otherwise if we're not paused and we have data ready, return it
            if self.running and self.check_ready():
                inputs = [s.get_nowait() for s in self.sources]

                if inputs and all(reip.CLOSE.check(x) for x, meta in inputs):
                    self.signal = reip.CLOSE  # block will send to sinks
                    self.close()
                    self.next()
                    continue

                if inputs and any(reip.TERMINATE.check(x) for x, meta in inputs):
                    self.signal = reip.TERMINATE  # block will send to sinks
                    self.terminate()
                    self.next()
                    continue

                t_last = time.time()
                yield prepare_input(inputs)
                if self.auto_next:
                    self.next()

            # if we are out of data and the stream is closed, stop iterating.
            elif not self.should_wait:
                return

            time.sleep(self._delay)
        # the only time this runs is when loop stops iterating.
        # notice that close and terminate all return, they don't break
        # so basically, the only time this is run is if we set a run duration
        # and we exceed that duration.
        self.signal = reip.CLOSE

    def retry(self):
        self._retry = True

    def next(self):
        if not self._retry:
            for s in self.sources:
                s.next()
        self._retry = False

    def open(self):
        self.should_wait = True
        self.terminated = False
        return self

    def close(self):
        self.should_wait = False
        return self

    def nowait(self, flag=True):
        self.should_wait = not flag
        return self

    def pause(self):
        self.running = False

    def resume(self):
        self.running = True

    def terminate(self):
        self.terminated = True

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    # pre-input

    def check_ready(self):
        '''Check if we're ready to send the inputs to the block.'''
        return all(not s.empty() for s in self.sources)

    # Manually get current items.

    def get(self, check=True):
        return (
            prepare_input([s.get_nowait() for s in self.sources])
            if check and self.check_ready() else None)


    @classmethod
    def make_loop(cls, duration=None, max_rate=None, delay=None):
        '''A master loop function that will contain'''
        return iters.throttled(
            iters.timed(iters.loop(), duration),
            max_rate, delay or cls._delay)

    @classmethod
    def from_block_sources(cls, block, max_rate=None, auto_next=False, **kw):
        '''Generate a stream using a block's sources.

        NOTE: this is unsafe as a public interface, because if you're using
        the same source instances in multiple places, the calls to `.next()` will
        interfere and you'll end up skipping items. That is why `auto_next` is set
        to `False`. For now, this is just used internally when creating a block.
        '''
        return cls(
            block.sources, auto_next=auto_next,
            max_rate=max_rate or block.max_rate, **kw)

    @classmethod
    def from_block(cls, block, max_rate=None, **kw):
        '''Generate a stream using sources generated from a block's sinks.'''
        return cls(
            [sink.gen_source() for sink in block.sinks],
            max_rate=max_rate or block.max_rate, **kw)

    # Stream slicing

    @property
    def data(self):
        return StreamSlice(self.sources, key='data')

    @property
    def meta(self):
        return StreamSlice(self.sources, key='meta')

    def __getitem__(self, index):
        return StreamSlice(self.sources)[index]



class StreamSlice(Stream):
    '''Allows you to take a stream and select to only return a certain output
    or only the metadata.

    TODO: currently this will produce unexpected results if you were to iterate over
    multiple StreamSlices because they drop the buffers that they're not interested in.
    A fix for this would be to generate a new source with its own Pointer objects.

    TODO: also, this could be optimized by not deserializing data if we are only requesting meta.

    Examples:
    >>> # creating 4 different stream slices
    >>> full = B.Constant(5).stream_output()
    >>> data = B.Constant(5).stream_output().data
    >>> data0 = B.Constant(5).stream_output().data[0]
    >>> meta = B.Constant(5).stream_output().meta

    >>> # ignore the fact that dicts are not hashable, this is for illustration.
    >>> with reip.default_graph().run_scope(duration=1):
    ...     assert set(full) == { ([5], {}) }  # everything, the default
    ...     assert set(data) == { [5] }        # all data buffers
    ...     assert set(full) == { 5 }          # only the first buffer
    ...     assert set(full) == { {} }         # only meta dicts

    '''
    def __init__(self, sources, key=None, index=slice(None), *a, **kw):
        super().__init__(sources, *a, **kw)
        self._slice_key = key
        self._slice_index = index

    def __iter__(self):
        for data, meta in super().__iter__():
            if self._slice_index is not None:
                data = data[self._slice_index]
            if self._slice_key == 'data':
                yield data
            elif self._slice_key == 'meta':
                yield meta
            else:
                yield data, meta

    def __getitem__(self, index):
        self._slice_index = index
        return self


def prepare_input(inputs):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, meta = zip(*inputs) if inputs else ((), ())
    return (
        # XXX: ... is a sentinel for empty outputs - how should we handle them here??
        #      if there's a blank in the middle
        [b for bs in bufs for b in reip.util.as_list(bs) if b is not reip.BLANK],
        reip.util.Meta({}, *meta[::-1]))
