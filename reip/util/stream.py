import time
import copy
import reip
from reip.util import text, iters
from reip.block import prepare_input, Throttler, construct_signal_indices


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
    _delay = 1e-4
    def __init__(self, sources, 
                 auto_next=True, wait=True,
                 squeeze=False, slice_key=None, 
                 timeout=None, duration=None,  max_rate=None, limit=None,
                 when=None, 
                 _sw=None, 
                 name=''):
        self.state = reip.util.states.States({
            'active': {'waiting', 'reading', 'paused'},
            None: {'terminated', 'should_wait'},
        })
        self.state.should_wait(wait)
        self.name = name or ''
        self.sources = sources
        self.__source_signals = [None]*len(sources)

        self.auto_next = auto_next
        self.timeout = timeout
        self.limit = limit
        self.__throttler = Throttler(max_rate)
        self.duration = duration

        self._squeeze = squeeze
        self._slice_key = slice_key
        
        self._sw = _sw or reip.util.Stopwatch(str(self))
        self.__source_process_condition = all if when is None else when
        


    def __str__(self):
        return '<{}({}) {} available={}>'.format(
            self.__class__.__name__, self.name,
            self.state, [len(s) for s in self.sources],
        )

    def sources_available(self):
        '''Check the sources to determine if we should call process.'''
        return not self.sources or self.__source_process_condition(not s.empty() for s in self.sources)

    def __iter__(self):
        wait_t0 = 0
        t0 = time.time()
        count = 0
        with self.state.active, self.__throttler as throttle:
            while True:
                # check if we are still in a configured state
                if not self.state.active:
                    # if terminated, don't finish up
                    if self.state.terminated:
                        break
                    # only finish up if there are sources that have items left to process
                    if not self.sources or not self.sources_available():
                        break
                    # otherwise, just finish up processing what's left
                    # XXX: what to do with circular block connections - it will never exit....


                # exit after a maximum duration
                if self.duration and time.time() - t0 > self.duration:
                    return
                # add a small delay
                time.sleep(self._delay)
                # check if we're paused
                if self.state.paused:
                    continue
                # check if we're throttling
                if throttle():
                    continue
                # check source availability
                if not self.sources_available():
                    if not self.state.waiting:
                        if not self.state.should_wait:
                            return
                        self.state.waiting()
                        wait_t0 = time.time()
                    else:
                        if self.timeout is not None and wait_t0 and time.time() - wait_t0 > self.timeout:
                            raise TimeoutError("Waiting for sources timed out after {} seconds.".format(self.timeout))
                    continue
                wait_t0 = 0
                self.state.waiting(False)

                # good to go!
                with self.state.reading:
                    # get inputs
                    with self._sw('source'):
                        # pull sources
                        inputs = self.__read_sources()
                        if inputs is None or not self.state.reading:  # check if we exited based on the inputs
                            continue

                        # buffer modifications (ignore meta / select index)
                        if self._squeeze and len(self.sources) == 1:
                            inputs = inputs[0][0], inputs[1]
                        if self._slice_key:
                            if self._slice_key == 'data':
                                inputs = inputs[0]
                            elif self._slice_key == 'meta':
                                inputs = inputs[1]

                        yield inputs
                        count += 1
                        if self.limit and count >= self.limit:
                            return
                        if self.auto_next:
                            self.next()

    def __read_sources(self):
        '''Get the next batch of data from each source.'''
        inputs = [s.get_nowait() for s in self.sources]
        # check inputs
        recv_close = False
        for data, source in zip(inputs, self.sources):
            if data is None:
                continue
            x, meta = data

            # handle signals
            if reip.CLOSE == x:  # XXX: how to handle - wait for all to close?
                source.next()
                self.close()
                recv_close = True
            if reip.TERMINATE == x:
                source.next()
                self.terminate()
                recv_close = True
        if recv_close:
            return

        buffers, meta = prepare_input(inputs)
        return buffers, meta

    def _reset(self):
        self.state.reset()

    def pause(self):
        self.state.paused(True)

    def resume(self):
        self.state.paused(False)

    def open(self):
        self.state.active(True)
        self.state.terminated(False)
        return self

    def close(self):
        self.state.active.request(False)

    def terminate(self):
        self.state.active.request(False)
        self.state.terminated()

    def nowait(self, flag=True):
        self.state.should_wait(not flag)
        # self.timeout = 0 if flag is True else None if flag is False else flag
        return self

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def source_signal(self, signals):
        '''Send signals to the sources.
        
        Arguments:
            signals (list): Signals for each source (by position). If a single signal is passed (instead of a list of signals), 
                it will be sent to all sources. Possible signals:
                * ``reip.RETRY``: Retry the last input for this source.
                * ``None``: Don't send a signal for this source.
        '''
        # global signal
        if isinstance(signals, (reip.Token, str)):
            signals = [signals] * len(self.sources)
        # too many signals
        elif len(signals) > len(self.sources):
            raise RuntimeError('Too many signals for sources. Got {}, expected ≤{}.'.format(
                len(signals), len(self.sources)))
        # send signals
        for i, (_, sig) in enumerate(zip(self.__source_signals, signals)):
            self.__source_signals[i] = sig

    def retry_source(self, *indices):
        '''Prettier way of doing ``self.source_signal([reip.RETRY, None, reip.RETRY])``.
        Instead it's ``self.retry_source(0, 2)``.
        '''
        self.source_signal(construct_signal_indices(
            reip.RETRY, *indices, signals=list(self.__source_signals)))

    def next(self):
        # send signals to any sources
        for i, src in enumerate(self.sources):
            if reip.RETRY == self.__source_signals[i]:
                pass
            else:
                src.next()
            self.__source_signals[i] = None
        return self


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
    def from_block(cls, block, max_rate=None, duration=None, when=None,
                   timeout=None, name=None, **kw):
        '''Generate a stream using sources generated from a block's sinks.'''
        return cls(
            [sink.gen_source(**kw) for sink in block.sinks],
            max_rate=max_rate or block.max_rate, when=None,
            duration=duration, timeout=timeout,
            name=name or block.name)

    # Stream slicing

    '''Allows you to take a stream and select to only return a certain output
    or only the metadata.

    TODO: currently this will produce unexpected results if you were to iterate over
    multiple StreamSlices because they don't copy sources.
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

    @property
    def data(self):
        stream = copy.copy(self)
        stream._slice_key = 'data'
        return stream

    @property
    def meta(self):
        stream = copy.copy(self)
        stream._slice_key = 'meta'
        return stream

    def __getitem__(self, index):
        stream = copy.copy(self)
        stream.sources = reip.util.as_list(self.sources[index])
        stream._squeeze = stream._squeeze or not isinstance(index, slice)
        return stream
