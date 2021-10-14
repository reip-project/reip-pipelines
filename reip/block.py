'''This is where I'm experimenting with state machine mechanics in the context of a block.

I'm starting with a striped down version that doesn't handle connections or anything atm.
'''
import time
import reip
from contextlib import contextmanager
import remoteobj
from reip.util import text
from reip.exceptions import ExceptionTracker, WorkerExit


class _BlockConnectable:
    '''This is a general base class that provides the operators for connecting blocks/sinks together.
    
    The only method that a subclass must implement is ``__call__``.
    '''
    def __call__(self, *others, **kw):
        '''Connect other block sinks to this blocks sources.'''
        raise NotImplementedError

    def to(self, *others, squeeze=True, **kw):
        '''Connect this blocks sinks to other blocks' sources'''
        outs = [other(self, **kw) for other in others]
        return outs[0] if squeeze and len(outs) == 1 else outs

    def __or__(self, other):
        '''Connect blocks using Unix pipe syntax.'''
        return self.to(*reip.util.as_list(other))

    def __ror__(self, other):
        '''Connect blocks using Unix pipe syntax.'''
        return self(*reip.util.as_list(other))

    def __getitem__(self, key):
        return _BlockSinkView(self, key)


class _BlockSinkView(_BlockConnectable):
    '''This is so that we can select a subview of a block's sinks. This is similar
    in principal to numpy views. The alternative is to store the state on the original
    object, but that would have unintended consequences if someone tried to create two
    different views from the same block.
    '''
    def __init__(self, block, idx):
        self.block = block
        # get the list of sources that this block points to.
        self.index = slice(idx, idx+1) if isinstance(idx, int) else idx
        self.sinks = sinks = self.block.sinks[idx]
        self.sink = sinks[0] if len(sinks) else None

    def __call__(self, *a, **kw):
        return self.block(*a, index=self.index, **kw)

    def __iter__(self):
        yield from self.sinks


# def get_indices(i, n):
#     '''Given an index, list of indices, or a slice, return a list of indices.'''
#     i = slice(i, None) if isinstance(i, int) else slice(n) if i is None else i
#     if isinstance(i, slice):
#         i = list(range(i.start or 0, min(i.stop or n, n), i.step or 1))
#     return [n+ii if ii < 0 else ii for ii in i]

def iter_idx(i, n):
    '''This converts any index passed to a list into an iterable.

    >>> assert list(iter_idx(5)) == [5]                              # alist[5]
    >>> assert list(iter_idx(slice(5))) == [0, 1, 2, 3, 4]           # alist[:5]
    >>> assert list(iter_idx(slice(None, None, 2), 6)) == [0, 2, 4]  # alist[::2]
    '''
    if i is None:
        i = slice(n)
    if isinstance(i, int):
        # i = slice(i, 0) if i < 0 else slice(i, n)
        yield i
        return
    if isinstance(i, slice):
        start, stop, step = i.start or 0, i.stop, i.step or 1
        stop = (-1 if n is None else n) if stop is None else stop
        while stop == -1 or start < stop:
            yield start
            start += step
        return
    yield from i
    


class Block(_BlockConnectable):
    USE_META_CLASS = True
    EXTRA_KW = False
    KW_TO_ATTRS = True
    _delay = 1e-4
    _wait_delay = 1e-2
    _agent = None
    processed = generated = 0
    n_inputs = n_outputs = 1

    def __init__(self, 
                 n_inputs=None, n_outputs=None,
                 max_rate=None, should_process=all, log_level='debug', queue_length=100,
                #  extra_meta=None, 
                 max_processed=None, max_generated=None, extra_kw=None,
                 finish_processing_on_close=True, graph=None, name=None, **kw):
        self.name = reip.auto_name(self, name=name)
        self.parent_id, self.task_id = reip.Graph.register_instance(self, graph)
        self.task_id = None
        self.state = reip.util.states.States({
            'spawned': {
                'configured': {
                    'initializing': {},
                    'ready': {
                        'waiting': {},
                        'processing': {},
                        'paused': {},
                    },
                    'finishing': {},
                },
                'needs_reconfigure': {},
            },
            'done': {None: {'terminated': {}}},
            # unlinked states
            None: {'_controlling': {}}
        })

        self.__source_process_condition = should_process
        # self._extra_meta = extra_meta
        self.__max_processed = max_processed
        self.__max_generated = max_generated
        self.__finish_processing_on_close = finish_processing_on_close

        self._except = ExceptionTracker()
        self.__throttler = Throttler(max_rate)
        self._sw = reip.util.Stopwatch(self.name)
        self.log = reip.util.logging.getLogger(self, level=log_level)

        if n_inputs is not None:
            self.n_inputs = n_inputs
        if n_outputs is not None:
            self.n_outputs = n_outputs

        self.sources = [None]*self.n_inputs
        self.sinks = [
            reip.Producer(queue_length, task_id=self.task_id)
            for _ in range(self.n_outputs)
        ]

        if self.KW_TO_ATTRS:
            for k in reip.util.clsattrdiff(Block, self.__class__):
                if k in kw:
                    setattr(self, k, kw.pop(k))

        self.extra_kw = None
        if extra_kw is None:
            extra_kw = self.EXTRA_KW
        if extra_kw:
            self.extra_kw = kw
        elif kw:
            raise TypeError("{} got unexpected arguments: {}".format(self, ', '.join(kw)))

    def __str__(self):
        return '[B({})[{}/{}]{}]'.format(self.name, len(self.sources), len(self.sinks), self.state)

    # def status(self):
    #     return str(self)

    # compat - these methods/properties are all needed by graphs/tasks

    @property
    def _thread(self):
        return self._agent

    @property
    def max_rate(self):
        return self.__throttler.max_rate

    @max_rate.setter
    def max_rate(self, max_rate):
        self.__throttler.max_rate = max_rate

    @property
    def ready(self):
        return bool(self.state.ready.value)

    @property
    def running(self):
        return bool(not self.state.paused)

    @property
    def done(self):
        return bool(self.state.done.value)

    @property
    def terminated(self):
        return bool(self.state.terminated)

    @property
    def error(self):
        # return self._except.caught
        return self._except.exception is not None

    def raise_exception(self):
        self.check_agent_exception()

    @property
    def _exception(self):
        return self._except.exception

    __BASE_EXPORT_PROPS = ['_sw', 'state', '_except', 'processed', 'generated']
    __BLOCK_EXPORT_PROPS__ = []
    def __export_state__(self, **kw):
        return dict((
            (k, getattr(self, k, None)) for k in 
            self.__BASE_EXPORT_PROPS + self.__BLOCK_EXPORT_PROPS__), **kw)

    def __import_state__(self, state):
        for k, v in state.items():
            try:
                x, ks = self, k.lstrip('!').split('.')
                for ki in ks[:-1]:
                    x = getattr(x, ki)
                setattr(x, ks[-1], v)
            except AttributeError:
                raise AttributeError('Could not set attribute {} = {}'.format(k, v))

    def output_stream(self, **kw):
        '''Create a Stream iterator which will let you iterate over the
        outputs of a block.'''
        from reip.util.stream import Stream
        return Stream.from_block(self, **kw)


    # Data Interface

    def init(self):
        '''Initialize the block.'''

    def sources_available(self):
        '''Check the sources to determine if we should call process.'''
        return not self.sources or self.__source_process_condition(not s.empty() for s in self.sources)

    def process(self, *xs, meta=None):
        '''Process data.'''
        return xs, meta

    def finish(self):
        '''Cleanup.'''

    # Connection Interface

    def __call__(self, *others, index=slice(None), ignore_extra=False, **kw):
        '''Connect other block sinks to this blocks sources.
        If the blocks have multiple sinks, they will be passed as additional
        inputs.
        '''
        # gather all sinks
        sinks = []
        for other in others:
            # permit argument to be a block, a sink, or a list of sinks
            if isinstance(other, _BlockConnectable):
                sinks_i = other.sinks
            else:
                sinks_i = reip.util.as_list(other)
            sinks.extend(sinks_i)

        # handle special cases for the index value
        if index == 'next':  # start at the first missing source
            index = next(
                (i for i, s in enumerate(self.sources) if s is None),
                'append')
        if index == 'append':  # append a source to the end
            index = len(self.sources)
        if isinstance(index, int):  # if someone enters 0, they probably mean start at the first source
            index = slice(index, None)

        # create and add the source
        isinks = iter(sinks)
        for sink, i_src in zip(isinks, iter_idx(index, self.n_inputs)):
            # negative index
            if i_src < 0:
                i_src += len(self.sources)
            if i_src > len(self.sources) or i_src < 0:
                if self.n_inputs >= 0:
                    raise ValueError("Could not set source index {} with {} sources.".format(i_src, len(self.sources)))
                if i_src < 0:
                    i_src = max(-len(self.sources), i_src)
            # make sure the list is long enough
            while len(self.sources) <= i_src:
                self.sources.append(None)

            self.sources[i_src] = sink.gen_source(task_id=self.task_id, **kw)

        if not ignore_extra:
            extra_sinks = list(isinks)
            if extra_sinks:
                raise RuntimeError("Too many sinks ({} extra) to connect.".format(len(extra_sinks)))
        return self

    # Control Interface

    def run(self, duration=None, **kw):
        '''Run a block synchronously.'''
        with self.run_scope(**kw):
            self.wait(duration)

    @contextmanager
    def run_scope(self, raise_exc=True):
        '''Run a block while we are inside the context manager.'''
        try:
            self.spawn()
            yield self
        except KeyboardInterrupt:
            self.terminate()
        finally:
            self.join(raise_exc=raise_exc)

    def wait(self, duration=None):
        '''Wait until the block is done.'''
        for _ in reip.util.iters.timed(reip.util.iters.sleep_loop(self._delay), duration):
            if self.state.done:
                return True

    def spawn(self, wait=True, *, _controlling=True, _ready_flag=None, _spawn_flag=None):
        try:
            self.state.controlling = _controlling
            self.__check_source_connections()
            # spawn any sinks that need it
            for s in self.sinks:
                if hasattr(s, 'spawn'):
                    s.spawn()
            self.__reset_state()
            self.state.spawned.request()
            self._agent = remoteobj.util.thread(self.__agent_main, _spawn_flag=_spawn_flag, daemon_=True, raises_=False)
            self._agent.start()

            if wait:
                while self.state.spawned and not self.state.ready:
                    time.sleep(self._wait_delay)
            if self.state.controlling:
                self.check_agent_exception()
        finally:
            # thread didn't start ??
            if self._agent is None or not self._agent.is_alive():
                self.state.spawned(False)
                self.state.done()
        return self

    __timeout = 30
    def join(self, close=True, terminate=False, raise_exc=None, timeout=None):
        try:
            # close stream
            if close:
                self.close()
            if terminate:
                self.terminate()
            # join any sinks that need it
            for s in self.sinks:
                if hasattr(s, 'join'):
                    s.join()
            # close thread
            if self._agent is not None and self._agent.is_alive():
                self._agent.join(timeout=self.__timeout if timeout is None else timeout)
                self._agent = None
            if (self.state.controlling if raise_exc is None else raise_exc):
                self.check_agent_exception()
        finally:
            self.state.done()
        return self

    def close(self, propagate=True):
        self.state.done.request()
        if propagate:
            self.__send_sink_signal(reip.CLOSE)

    def terminate(self, propagate=True):
        self.state.done.request()
        self.state.terminated()
        if propagate:
            self.__send_sink_signal(reip.TERMINATE)

    def pause(self):
        self.state.paused(True)

    def resume(self):
        self.state.paused(False)

    # internal

    def __check_source_connections(self):
        '''Make sure that the connections to the block sources are valid.'''
        disconnected = [i for i, s in enumerate(self.sources) if s is None]
        if disconnected:
            raise RuntimeError(f"Sources {disconnected} in {self} not connected.")

        # check for exact source count
        if (self.n_inputs >= 0 and len(self.sources) != self.n_inputs):
            raise RuntimeError(
                f'Expected {self.n_inputs} sources '
                f'in {self}. Found {len(self.sources)}.')

    def check_agent_exception(self):
        '''Raise any exceptions caught during agent execution. Meant to be run after joining the block.'''
        self._except.raise_any()

    # internal state lifecycle

    def __reset_state(self):
        '''Reset the block state. This should be called to restore the block back to a blank state.'''
        self.state.reset()
        self.processed = 0
        self.generated = 0
        self.old_processed = 0
        self.old_time = time.time()
        self.__source_signals = [None] * len(self.sources)

    def __agentless_spawn(self):
        '''This is a way to spawn the block without spawning a thread. Just here for testing purposes.'''
        try:
            self.__reset_state()
            self.__agent_main()
        finally:
            pass

    def __agent_main(self, *, _spawn_flag=None, _ready_flag=None):
        '''This is the main agent loop that is called by the thread runner.
        This is where the high level operation happens (reconfiguration, restarting, etc.).'''
        if _spawn_flag:
            _spawn_flag.wait()
        with self._except:
            try:
                with self._sw(), self.state.spawned:  # , self._except(raises=False)
                    try:
                        while self.state.spawned:
                            self.log.info(self.state)
                            if not self.state.configured:
                                self.__reconfigure()
                            assert self.state.configured
                            self.__run_configured()
                        
                    except WorkerExit:
                        pass
                    finally:
                        self.state.configured(False)
            finally:
                # NOTE: I don't know the best way to handle setting terminated.
                #       because when we get here, done is enabled, but terminated 
                #       is still disabled in a high potential state.
                #       right now, I have 
                self.state.done()

    def __reconfigure(self):
        '''This updates the configuration and possibly respawns / re-inits 
        TODO: what to do here?'''
        self.state.configured()

    def __run_configured(self, duration=None, t0=None):
        '''This is the main loop of the block. This is where all of the magic happens.'''
        t0 = t0 or time.time()
        try:
            with self.state.initializing, self._sw('init'), self._except('init'):
                self.init()

            with self.state.ready, self.__throttler as throttle:
                while True:
                    # check if we are still in a configured state
                    if not self.state.configured:
                        # just exit quick, reconfigure, and come back
                        if self.state.needs_reconfigure:
                            break
                        # if terminated, don't finish up
                        if self.state.terminated:
                            break
                        # only finish up if there are sources that have items left to process
                        if not self.sources or not self.sources_available():
                            break
                        # otherwise, just finish up processing what's left
                        # XXX: what to do with circular block connections - it will never exit....
                        
                    # set a time limit
                    if duration and time.time() - t0 > duration:
                        break
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
                        self.state.waiting()
                        continue
                    self.state.waiting(False)

                    # good to go!
                    with self.state.processing:
                        # get inputs
                        with self._sw('source'):
                            inputs = self.__read_sources()
                            if inputs is None or not self.state.processing:  # check if we exited based on the inputs
                                continue
                            buffers, meta = inputs

                        # process each input batch
                        with self._sw('process'), self._except('process'): #
                            outputs = self.__process_buffer(buffers, meta)

                        # send each output batch to the sinks
                        with self._sw('sink'):
                            self.__send_to_sinks(outputs, meta)

        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
            self.terminate()
        finally:
            with self.state.finishing, self._sw('finish'), self._except('finish'):
                self.finish()


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

        buffers, meta = prepare_input(inputs, Block.USE_META_CLASS)
        return buffers, meta

    def __process_buffer(self, buffers, meta):
        '''Process the input buffers.'''
        # process and get outputs
        outputs = self.process(*buffers, meta=meta)

        # count the number of buffers received and processed
        self.processed += 1
        # limit the number of buffers
        if self.__max_processed and self.processed >= self.__max_processed:
            self.close(propagate=True)
        return outputs

    def __send_to_sinks(self, outputs, input_meta):
        '''Send the outputs to the sink.'''
        for outs in (outputs if is_generator(outputs) else iter((outputs,))):
            if outs is None:  # next
                continue

            # convert outputs to a consistent format
            outs = prepare_output(outs, input_meta, as_meta=Block.USE_META_CLASS)
            # pass to sinks
            for sink, out in zip(self.sinks, outs):
                if sink is not None and out is not None:
                    sink.put(out)

            # count the number of buffers generated
            self.generated += 1
            # limit the number of buffers
            if self.__max_generated and self.generated >= self.__max_generated:
                self.close(propagate=True)

        # send signals to any sources
        for i, src in enumerate(self.sources):
            if reip.RETRY == self.__source_signals[i]:
                pass
            else:
                src.next()
            self.__source_signals[i] = None

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

    def __send_sink_signal(self, signal, block=True, meta=None, timeout=1):
        '''Emit a signal to all sinks. e.g. tell all sinks to ``reip.CLOSE`` / ``reip.TERMINATE``.'''
        for sink in self.sinks:
            if sink is not None:
                try:
                    sink.put((signal, meta or {}), block=block, timeout=timeout)
                except TimeoutError:
                    reip.util.print_stack()
                    print('timeout sending', signal, 'to', sink)
                    pass  # ???


    # experimental source signal interface

    def retry_sources(self, *indices):
        '''Prettier way of doing ``self.source_signal([reip.RETRY, None, reip.RETRY])``.
        Instead it's ``self.retry_sources(0, 2)``  or ``self.retry_sources()`` for all sources.
        '''
        self.source_signal(construct_signal_indices(
            reip.RETRY, *indices, signals=list(self.__source_signals)))


    # String representations (basically just copied from old version)

    def short_str(self):
        return '[B({})[{}/{}]({})]'.format(
            self.name, len(self.sources), len(self.sinks), self.state)

    def stats(self):
        total_time = self._sw.stats().sum if '' in self._sw else 0
        init_time = self._sw.stats("init").sum if 'init' in self._sw else 0
        finish_time = self._sw.stats("finish").sum if 'finish' in self._sw else 0

        return {
            'name': self.name,
            'total_time': total_time,
            'processed': self.processed,
            'speed': self.processed / (total_time - init_time - finish_time) if total_time else 0,
            'dropped': [getattr(s, "dropped", None) for s in self.sinks],
            'skipped': [getattr(s, "skipped", None) for s in self.sources],
            'n_in_sources': [len(s) if s is not None else None for s in self.sources],
            'n_in_sinks': [len(s) if s is not None else None for s in self.sinks],
            'sw': self._sw,
            # 'exception': self._exception,
            # 'all_exceptions': self._except._groups,
        }

    def summary(self):
        return text.block_text(
            text.green(str(self)),
            'Sources:',
            text.indent(text.b_(*(f'- {s}' for s in self.sources)) or None, w=4)[2:],
            '',
            'Sinks:',
            text.indent(text.b_(*(f'- {s}' for s in self.sinks)) or None, w=4)[2:],
            ch=text.blue('*'), n=40,
        )

    def status(self):
        '''
        e.g. `Block_123    +   2 buffers (2.09 x/s),   9 total (1.47 x/s avg),  sources=[1], sinks=[0]`
        '''
        n = self.processed
        total_time = self._sw.total() # self._sw.elapsed()
        init_time = self._sw.stats("init").sum if 'init' in self._sw else 0
        speed_avg = n / (total_time - init_time)

        n_new = n - self.old_processed
        speed_now = n_new / (time.time() - self.old_time)
        self.old_processed, self.old_time = n, time.time()

        n_src = [len(s) if s is not None else None for s in self.sources]
        n_snk = [len(s) if s is not None else None for s in self.sinks]
        dropped = [getattr(s, 'dropped', None) for s in self.sinks]

        return f'{self.name}\t + {n_new:3} buffers ({speed_now:,.2f} x/s), {n:5} total ({speed_avg:,.2f} x/s avg), sources={n_src}, sinks={n_snk}, dropped={dropped}'

    def stats_summary(self):
        stats = self.stats()
        # return text.block_text(
        return text.b_(
            # block title
            '\nStats for {summary_banner}',
            # any exception, if one was raised.
            text.red('({}) {}'.format(type(self._exception).__name__, self._exception))
            if self._exception else None,
            # basic stats
            'Processed {processed} buffers in {total_time:.2f} sec. ({speed:.2f} x/s)',
            'Dropped: {dropped}  Skipped: {skipped}  Left in Queue: in={n_in_sources} out={n_in_sinks}',
            # timing info
            # self._sw, ch=text.blue('*')).format(
            self._sw).format(
                summary_banner=text.red(self) if self.error else text.green(self),
                **stats)




# Helpers
#####################




def prepare_input(inputs, as_meta=True, expected_inputs=-1):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, metas = tuple(zip(*([buf if buf is not None else (None, {}) for buf in inputs]))) or ((), ())

    if as_meta:
        metas = reip.Meta(inputs=metas)
    else:
        if len(metas) == 1:  # expected_inputs and expected_inputs == 1 and 
            metas = metas[0]
    return list(bufs), metas


def prepare_output(outputs, input_meta=None, as_meta=True):
    '''Take the inputs from block.process and prepare to be passed to block.sinks.
    >>> x, meta
    >>> [(x, meta), (x2, meta)]
    '''
    if not outputs:
        return []

    if isinstance(outputs, (list, tuple)):
        # detect single output shorthand
        if len(outputs) >= 2 and isinstance(outputs[1], (dict, reip.util.Meta)):
            outputs = [outputs]

    # normalize metadata
    outs = []
    for out in outputs:
        if out is None:
            outs.append(None)
            continue

        x, meta = out
        if meta is None:
            meta = reip.util.Meta() if as_meta else {}
        if as_meta and not isinstance(meta, reip.util.Meta):
            meta = reip.util.Meta(meta, input_meta.inputs)
        outs.append((x, meta))
    return outs


def construct_signal_indices(signal, *indices, signals=None):
    '''Utility for setting signals for certain indices.'''
    if not indices:  # single signal for everything
        return signal
    if signals is None:
        signals = [None]*(max(indices)+1)
    for i in indices:
        signals[i] = signal
    return signals


def is_generator(iterable):
    return not hasattr(iterable,'__len__') and hasattr(iterable,'__iter__')


class RelativeThrottler:
    '''This was my first draft, but it makes sure that the time between calls is at least
    1 / max_rate, but this inevitably results in drift. (Meaning if one call is later, 
    everything is pushed later accordingly.)

    But realistically, we want it operating on a clock, meaning that if one call takes longer
    the next call will still try to happen on a multiple of the max rate (from the start time)

    Example Timings:
        RelativeThrottler: 0  1  1.2  2.2  3.3  4.3
        ClockThrottler:    0  1  1.2  2    3.1  4
    '''
    t_last = 0
    def __init__(self, max_rate=None, rate_chunk=0.4):
        self.max_rate = max_rate
        self.rate_chunk = rate_chunk

    def __enter__(self):
        self.t_last = 0#time.time() - (self.max_rate or 0)
        return self
    
    def __exit__(self, *a):
        pass

    def __call__(self):
        # NOTE: sleep in chunks so that if we have a really high
        #       interval (e.g. run once per hour), then we don't
        #       have to wait an hour to shut down
        if self.max_rate:
            ti = time.time()
            dt = max(0, 1 / self.max_rate - (ti - self.t_last))
            if self.rate_chunk:
                dt = min(dt, self.rate_chunk)
            if dt:
                time.sleep(dt)
            if ti < self.t_last + 1 / self.max_rate:  # return True, will notify that we should keep waiting
                return True
            self.t_last = time.time()
        return False

class ClockThrottler:
    t_last = 0
    def __init__(self, max_rate=None, rate_chunk=0.4):
        self.max_rate = max_rate
        self.rate_chunk = rate_chunk

    def __enter__(self):
        self.t_start = time.time()
        self.i_last = -1
        return self
    
    def __exit__(self, *a):
        pass

    def __call__(self):
        # NOTE: sleep in chunks so that if we have a really high
        #       interval (e.g. run once per hour), then we don't
        #       have to wait an hour to shut down
        rate = self.max_rate
        if rate:
            interval = 1 / rate
            ti = time.time()
            i = (ti - self.t_start) // interval
            if i == self.i_last:
                dt = max(0, interval - (ti - i * interval))
                if dt:
                    time.sleep(min(dt, self.rate_chunk) if self.rate_chunk else dt)
            
                i = (time.time() - self.t_start) // interval
                if i == self.i_last:
                    return True
            self.i_last = i
        return False

Throttler = ClockThrottler


if __name__ == '__main__':
    class MyBlock(Block):
        raises=False
        n=10
        
        def init(self):
            self.i = 0

        def process(self, meta):
            self.i += 1
            if self.i > self.n:
                if self.raises:
                    raise ValueError('Agh hi!')
                self.terminate()
            self.log.info(self.i)
            return self.i, {'n': self.n}
    
    class MyBlock2(Block):
        def process(self, *xs, meta):
            return sum(xs)*2, meta

    class Debug(Block):
        def process(self, x, meta):
            self.log.info((x, dict(meta)))
            return x, meta
            
    def simple(raises=False, n=10, rate=3):
        with reip.Graph() as g:
            block = MyBlock(n_inputs=0, max_rate=rate, raises=raises, n=n, max_processed=15)
            block2 = MyBlock2()([block])
            block.to().to(Debug())
        # @block.state.add_callback
        # def log_changes(state, value):
        #     block.log.info('{} -> {}'.format(state, value))
        # block._Block__spawned()
        g.run(stats_interval=10)
        print(block.state.treeview(), flush=True)

    def task(raises=False, n=10, rate=3):
        with reip.Graph() as g:
            with reip.Task():
                block = MyBlock(n_inputs=0, max_rate=rate, raises=raises, n=n, max_processed=15)
                block.to(MyBlock2()).to(Debug())

        def log_state_changes(b, state):
            @state.add_callback
            def log(state, value):
                b.log.info('{} -> {}'.format(state, value))
            return log
        for b in g.iter_blocks():
            print(b)
            print(b.state.terminated._callbacks)
            log_state_changes(b, b.state.terminated)
            print(b.state.terminated._callbacks)
            log_state_changes(b, b.state.done)

        try:
            g.run(stats_interval=10)
        finally:
            print(g)
            for b in g.iter_blocks():
                print(b.name)
                print(b._except)
                print(b.state.treeview(), flush=True)
                print()

    import fire
    fire.Fire()
