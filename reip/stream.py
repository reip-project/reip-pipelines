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
    running = True
    terminated = False
    signal = None
    def __init__(self, sources, get_loop=None, auto_next=True, should_wait=True,
                 timeout=None, name='', **kw):
        self.name = name or ''
        self.sources = sources
        self._loop_kw = kw
        self._get_loop = get_loop
        self.auto_next = auto_next
        self.should_wait = should_wait
        self.timeout = timeout

    def __str__(self):
        state = (
            ' '.join((
                'will-wait' * self.should_wait,
                'terminated' * self.terminated))
            or ('running' if self.running else 'paused'))

        # srcs = ''.join(f'\n{s}' for s in self.sources)
        return f'<{self.__class__.__name__}({self.name}) {state} available={[len(s) for s in self.sources]}>'

    def get_loop(self, **kw):
        return (
            self._get_loop(**kw) if callable(self._get_loop) else
            self.default_loop(**dict(self._loop_kw, **kw)))

    @classmethod
    def default_loop(cls, duration=None, max_rate=None, delay=None):
        '''A master loop function that will contain'''
        delay = delay or cls._delay
        return iters.throttled(
            iters.timed(iters.sleep_loop(delay), duration),
            max_rate, delay)

    def __iter__(self):
        self._reset()
        for _ in self.get_loop():
            inputs = self.get()
            if self.terminated or (inputs is None and not self.should_wait):
                return
            if inputs is not None:
                yield inputs
                if self.auto_next:
                    self.next()
        # the only time this runs is when self.loop stops iterating.
        self.signal = reip.CLOSE

    def poll(self, block=True, timeout=None): # FIXME: return value? exception? ?????
        '''Returns whether or not the stream is ready to pull from.'''
        # for streams with no sources, there's nothing to wait for
        for _ in iters.timed(iters.sleep_loop(), timeout or self.timeout):
            if self.terminated:
                return False
            if not self.sources and not self.should_wait:
                return False
            if self.running and all(not s.empty() for s in self.sources):
                return True
            if not block or not self.should_wait:
                return False
        return False

    def get(self, block=True, timeout=None):
        # FIXME loop because if we see any signals, _get will be None and we'll have to
        #       try again. But we also
        for _ in iters.timed(iters.sleep_loop(), timeout or self.timeout):
            ready = self.poll(block=block, timeout=timeout)
            if not ready:  # either block=False or timeout
                return
            value = self._get()
            if value is not None:
                return value
            # otherwise it was a signal, retry

    def _get(self):
        inputs = [s.get_nowait() for s in self.sources]

        if inputs and all(reip.CLOSE.check(x) for x, meta in inputs):
            self.signal = reip.CLOSE  # block will send to sinks
            self.next()
            self.close()
            return

        if inputs and any(reip.TERMINATE.check(x) for x, meta in inputs):
            self.signal = reip.TERMINATE  # block will send to sinks
            self.next()
            self.terminate()
            return
        return prepare_input(inputs)

    def retry(self):
        self._retry = True
        return self

    def next(self):
        if not self._retry:
            for s in self.sources:
                s.next()
        self._retry = False
        return self

    def _reset(self):
        self.signal = None
        self.terminated = False
        self.resume()
        return self

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
        return self

    def resume(self):
        self.running = True
        return self

    def terminate(self):
        self.terminated = True
        return self

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    # pre-input

    def check_signals(self, outputs):
        if self.sources:
            if any(any(t.check(o) for t in reip.SOURCE_TOKENS) for o in outputs):
                # check signal values
                if len(outputs) > len(self.sources):
                    raise RuntimeError(
                        f'Too many signals for sources in {self}. '
                        f'Got {len(outputs)}, expected a maximum '
                        f'of {len(self.sources)}.')
                # process signals
                for s, out in zip(self.sources, outputs):
                    if out == reip.RETRY:
                        pass
                    else:
                        s.next()
                return True
        return False

    @classmethod
    def from_block_sources(cls, block, max_rate=None, auto_next=False, name=None, **kw):
        '''Generate a stream using a block's sources.

        NOTE: this is unsafe as a public interface, because if you're using
        the same source instances in multiple places, the calls to `.next()` will
        interfere and you'll end up skipping items. That is why `auto_next` is set
        to `False`. For now, this is just used internally when creating a block.
        '''
        return cls(
            block.sources, auto_next=auto_next,
            max_rate=max_rate or block.max_rate,
            name=name or block.name, **kw)

    @classmethod
    def from_block(cls, block, max_rate=None, duration=None, delay=None,
                   timeout=None, name=None, **kw):
        '''Generate a stream using sources generated from a block's sinks.'''
        return cls(
            [sink.gen_source(**kw) for sink in block.sinks],
            max_rate=max_rate or block.max_rate, delay=delay,
            duration=duration, timeout=timeout,
            name=name or block.name)

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
    >>> full = B.Constant(5).output_stream()
    >>> data = B.Constant(5).output_stream().data
    >>> data0 = B.Constant(5).output_stream().data[0]
    >>> meta = B.Constant(5).output_stream().meta

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