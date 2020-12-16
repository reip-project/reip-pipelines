import time
import threading
import warnings
from contextlib import contextmanager
import remoteobj

import reip
from reip.stores import Producer
from reip.util import text, Meta


__all__ = ['Block']


class _BlockSinkView:
    def __init__(self, block, idx):
        self._block = block
        self._index = idx

    @property
    def item(self):  # can be a single sink, or multiple i.e. block[0] or block[:2]
        return self._block.sinks[self._index]

    @property
    def items(self):  # always a list
        return reip.util.as_list(self.item)

    def __iter__(self):  # iterate over sink
        return iter(self.items)

    def __getitem__(self, key):  # get sub index
        return self.items[key]


class Block:
    '''This is the base instance of a block.

    Arguments:
        queue (int): the maximum queue length.
        n_inputs (int, or None): the number of sources to expect. If None,
            it will accept a variable number of sources.
        n_outputs (int): the number of sinks to expect.
             - If `n_outputs=0`, then there will be a single sink, that outputs no
               buffer value, but does output metadata.
               e.g.
               ```python
               # block 1
               return {'just some metadata': True}
               # or
               return [], {'just some metadata': True}

               # block 2
               def process(self, meta):  # no buffer value
                   assert meta['just some metadata'] == True
               ```
             - If `n_outputs=None`, then the block will have no sinks.

        blocking (bool): should the block wait for sinks to have a free space
            before processing more items?
        max_rate (int): the maximum number of iterations per second. If the block
            processes items any faster, it will throttle and sleep the required
            amount of time to meet that requirement.
            e.g. if max_rate=5, then an iteration will take at minimum 0.2s.
        graph (reip.Graph, reip.Task, or False): the graph instance to be added to.
        name ()
    '''
    _thread = None
    _stream = None
    _delay = 1e-6
    parent_id, task_id = None, None
    started = ready = done = _terminated = False
    processed = 0
    controlling = False
    max_rate = None

    def __init__(self, n_inputs=1, n_outputs=1, queue=1000, blocking=False,
                 max_rate=None, min_interval=None, max_processed=None, graph=None, name=None,
                 source_strategy=all, extra_kw=False, log_level=None, **kw):
        self._except = remoteobj.LocalExcept(raises=True)
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.parent_id, self.task_id = reip.Graph.register_instance(self, graph)

        # sources and sinks
        # by default, a block takes a variable number of sources.
        # If a block has a fixed number of sources, you can specify that
        # and it will throw an exception when spawning if the number of
        # sources does not match.
        self._block_sink_queue_length = queue  # needed for set sink count
        self.n_expected_sources = n_inputs
        self.sources, self.sinks = [], []
        self.set_block_source_count(n_inputs)
        self.set_block_sink_count(n_outputs)
        # used in Stream class. Can be all(), any() e.g. source_strategy=all
        self._source_strategy = source_strategy

        if min_interval and max_rate:
            warnings.warn((
                'Both max_rate ({}) and min_interval ({}) are set, but are '
                'mutually exclusive (max_rate=1/min_interval). min_interval will'
                'be used.').format(max_rate, min_interval))
        if max_rate:
            self.max_rate = max_rate
        if min_interval:
            self.min_interval = min_interval
        self.max_processed = max_processed
        self._put_blocking = blocking
        if extra_kw:
            self.extra_kw = kw
        elif kw:
            raise TypeError('{} received {} unexpected keyword arguments: {}.'.format(
                self, len(kw), set(kw)))

        # block timer
        self._sw = reip.util.Stopwatch(str(self))
        self.log = reip.util.logging.getLogger(self, level=log_level)
        # signals
        self._reset_state()

    @property
    def min_interval(self):
        return self.max_rate

    @min_interval.setter
    def min_interval(self, value):
        self.max_rate = 1. / value if value is not None else value

    def set_block_source_count(self, n):
        # NOTE: if n is None, no resize will happen
        self.sources = reip.util.resize_list(self.sources, n, None)

    def set_block_sink_count(self, n):
        # NOTE: if n is None, no resize will happen
        new_sink = lambda: Producer(self._block_sink_queue_length, task_id=self.task_id)
        self.sinks = reip.util.resize_list(self.sinks, n, new_sink)

    def _reset_state(self):
        # state
        self.started = False
        self.ready = False
        self.done = False
        self._terminated = False
        # stats
        self.processed = 0
        self._sw.reset()
        self._except.clear()

    def __repr__(self):
        return '[Block({}): ({}/{} in, {} out; {} processed) - {}]'.format(
            self.name, sum(s is not None for s in self.sources),
            '?' if self.n_expected_sources is None else self.n_expected_sources,
            len(self.sinks), self.processed,
            self.block_state_name)

    @property
    def block_state_name(self):
        return (
            (type(self._exception).__name__
             if self._exception is not None else 'error') if self.error else
            ('terminated' if self.terminated else 'done') if self.done else
            ('running' if self.running else 'paused') if self.ready else
            'started' if self.started else '--'  # ??
        )  # add "uptime 35.4s"

    # Graph definition

    def __call__(self, *others, **kw):
        '''Connect other block sinks to this blocks sources.
        If the blocks have multiple sinks, they will be passed as additional
        inputs.
        '''
        j = 0
        for i, other in enumerate(others):
            # permit argument to be a block
            # permit argument to be a sink or a list of sinks
            if isinstance(other, Block):
                sinks = other.sinks
            elif isinstance(other, _BlockSinkView):
                sinks = other.items
            else:
                sinks = reip.util.as_list(other)

            if sinks:
                # make sure the list is long enough
                self.set_block_source_count(j + len(sinks))

                # create and add the source
                for j, sink in enumerate(sinks, j):
                    self.sources[j] = sink.gen_source(
                        task_id=self.task_id, **kw)
                j += 1  # need to increment cursor so we don't repeat last index
        return self

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

    def output_stream(self, **kw):
        '''Create a Stream iterator which will let you iterate over the
        outputs of a block.'''
        return reip.Stream.from_block(self, **kw)

    def __getitem__(self, key):
        return _BlockSinkView(self, key)

    # User Interface

    def init(self):
        '''Initialize the block.'''

    def process(self, *xs, meta=None):
        '''Process data.'''
        return xs, meta

    def finish(self):
        '''Cleanup.'''

    # main process loop

    # TODO common worker class
    def run(self, duration=None, **kw):
        with self.run_scope(**kw):
            self.wait(duration)

    @contextmanager
    def run_scope(self, raise_exc=True):
        try:
            self.spawn()
            yield self
        except KeyboardInterrupt:
            self.terminate()
        finally:
            self.join(raise_exc=raise_exc)

    def wait(self, duration=None):
        for _ in reip.util.iters.timed(reip.util.iters.sleep_loop(self._delay), duration):
            if self.done or self.error:
                return True

    def _main(self, _ready_flag=None, duration=None):
        '''The main thread target function. Handles uncaught exceptions and
        generic Block context management.'''
        try:
            with self._sw(), self._except(raises=False):
                try:
                    # profiler = pyinstrument.Profiler()
                    # profiler.start()
                    self.log.debug(text.blue('Starting...'))
                    time.sleep(self._delay)
                    # create a stream from sources with a custom control loop
                    self._stream = reip.Stream.from_block_sources(
                        self, name=self.name, _sw=self._sw,
                        strategy=self._source_strategy)
                    with self._stream:
                        # block initialization
                        with self._sw('init'), self._except('init'):
                            self.init()
                        self.ready = True
                        self.log.debug(text.green('Ready.'))
                        if _ready_flag is not None:
                            with self._sw('sleep'):
                                _ready_flag.wait()

                        loop = reip.util.iters.throttled(
                            reip.util.iters.timed(reip.util.iters.loop(), duration),
                            self.max_rate, delay=self._delay)
                        for _ in self._sw.iter(loop, 'sleep'):
                            inputs = self._stream.get()
                            if inputs is None:
                                break

                            # process each input batch
                            with self._sw('process'), self._except('process'):
                                buffers, meta = inputs
                                outputs = self.process(*buffers, meta=meta)
                            # send each output batch to the sinks
                            with self._sw('sink'):
                                self._send_to_sinks(outputs, meta)

                except KeyboardInterrupt:
                    if self.controlling:
                        self.log.info(text.yellow('Interrupting'))
                finally:
                    # finish up and shut down block
                    self.log.debug(text.yellow('Finishing...'))
                    # run block finish
                    with self._sw('finish'), self._except('finish', raises=False):
                        self.finish()
                    # propagate stream signals to sinks e.g. CLOSE
                    if self._stream.signal is not None:
                        self._send_sink_signal(self._stream.signal)
                    # profiler.stop()
                    # print(profiler.output_text(unicode=True, color=True))

        finally:
            self.done = True
            self.log.debug(text.green('Done.'))
            #pass
            # if _ready_flag is None:
            #     self.log.info(self.stats_summary())

    def _send_to_sinks(self, outputs, meta_in=None):
        '''Send the outputs to the sink.'''
        source_signals = [None]*len(self.sources)
        # retry all sources
        for outs in outputs if reip.util.is_iter(outputs) else (outputs,):
            if outs == reip.RETRY:
                source_signals = [reip.RETRY]*len(self.sources)
            elif outs == reip.CLOSE:
                self.close(propagate=True)
            elif outs == reip.TERMINATE:
                self.terminate(propagate=True)
            # increment sources but don't have any outputs to send
            elif outs is None:
                pass
            #     self._stream.next()
            # increment sources and send outputs
            else:
                # detect signals meant for the source
                if self.sources:
                    if outs is not None and any(any(t.check(o) for t in reip.SOURCE_TOKENS) for o in outs):
                        # check signal values
                        if len(outputs) > len(self.sources):
                            raise RuntimeError(
                                'Too many signals for sources in {}. Got {}, expected a maximum of {}.'.format(
                                    self, len(outputs), len(self.sources)))
                        for i, o in enumerate(outs):
                            if o is not None:
                                source_signals[i] = o
                        continue

                # convert outputs to a consistent format
                outs, meta = prepare_output(outs, input_meta=meta_in)
                # pass to sinks
                for sink, out in zip(self.sinks, outs):
                    if sink is not None:
                        sink.put((out, meta), self._put_blocking)

                # increment sources
                # self._stream.next()
                self.processed += 1
                # limit the number of blocks
                if self.max_processed and self.processed >= self.max_processed:
                    self.close(propagate=True)
        for src, sig in zip(self.sources, source_signals):
            if sig is reip.RETRY:
                pass
            else:
                src.next()


    def _send_sink_signal(self, signal, block=True, meta=None):
        '''Emit a signal to all sinks.'''
        self.log.debug(text.yellow(text.l_('sending', signal)))
        for sink in self.sinks:
            if sink is not None:
                sink.put((signal, meta or {}), block=block)

    # Thread management

    def spawn(self, wait=True, _controlling=True, _ready_flag=None):
        '''Spawn the block thread'''
        self.controlling = _controlling
        self.log.debug(text.blue('Spawning...'))
        # print(self.summary())

        self._check_source_connections()
        # spawn any sinks that need it
        for s in self.sinks:
            if hasattr(s, 'spawn'):
                s.spawn()
        self._reset_state()
        self.resume()
        self._thread = threading.Thread(target=self._main, kwargs={'_ready_flag': _ready_flag}, daemon=True)
        self._thread.start()

        if wait:
            self.wait_until_ready()
        if self.controlling:
            self.raise_exception()

    def _check_source_connections(self):
        '''Check if there are too many sources for this block.'''
        # check for any empty sources
        disconnected = [i for i, s in enumerate(self.sources) if s is None]
        if disconnected:
            raise RuntimeError(f"Sources {disconnected} in {self} not connected.")

        # check for exact source count
        if (self.n_expected_sources is not None
                and len(self.sources) != self.n_expected_sources):
            raise RuntimeError(
                f'Expected {self.n_expected_sources} sources '
                f'in {self}. Found {len(self.sources)}.')

    def remove_extra_sources(self, n=None):
        n = n or self.n_expected_sources
        if n is not None:
            self.sources = self.sources[:n]

    def wait_until_ready(self):
        '''Wait until the block is initialized.'''
        while not self.ready and not self.error and not self.done:
            time.sleep(self._delay)

    def join(self, close=True, terminate=False, raise_exc=None, timeout=None):
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
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if (self.controlling if raise_exc is None else raise_exc):
            self.raise_exception()

    def raise_exception(self):
        self._except.raise_any()

    def log_exception(self):
        for e in self._except.all():
            self.log.exception(e)

    @property
    def _exception(self):
        return self._except.last

    @property
    def all_exceptions(self):
        return self._except.all()

    def __export_state__(self):
        return {
            '_sw': self._sw,
            'started': self.started, 'ready': self.ready,
            'done': self.done, #'error': self.error,
            'terminated': self.terminated,
            # '_stream.terminated': self._stream.terminated,
            # '_stream.should_wait': self._stream.should_wait,
            # '_stream.running': self._stream.running,
            '_except': self._except,
        }

    def __import_state__(self, state):
        for k, v in state.items():
            try:
                x, ks = self, k.lstrip('!').split('.')
                for ki in ks[:-1]:
                    x = getattr(x, ki)
                setattr(x, ks[-1], v)
            except AttributeError:
                raise AttributeError('Could not set attribute {} = {}'.format(k, v))

    # State management

    def pause(self):
        if self._stream is not None:
            self._stream.pause()

    def resume(self):
        if self._stream is not None:
            self._stream.resume()

    def close(self, propagate=False):
        if self._stream is not None:
            self._stream.close()
        if propagate:
            self._send_sink_signal(reip.CLOSE)

    def terminate(self, propagate=False):
        if self._stream is not None:
            self._stream.terminate()
        if propagate:
            self._send_sink_signal(reip.TERMINATE)

    @property
    def error(self):
        return self._exception is not None

    # XXX: this is temporary. idk how to elegantly handle this
    @property
    def running(self):
        return self._stream.running if self._stream is not None else False

    @property
    def terminated(self):
        return self._terminated or (self._stream.terminated if self._stream is not None else False)

    @terminated.setter
    def terminated(self, value):
        self._terminated = value


    # debug

    def short_str(self):
        return '[B({})[{}/{}]({})]'.format(
            self.name, len(self.sources), len(self.sinks),
            self.block_state_name)

    def stats(self):
        total_time = self._sw.stats().sum if '' in self._sw else 0
        return {
            'name': self.name,
            'total_time': total_time,
            'processed': self.processed,
            'speed': self.processed / total_time if total_time else 0,
            'dropped': [getattr(s, "dropped", None) for s in self.sinks],
            'skipped': [getattr(s, "skipped", None) for s in self.sources],
            'n_in_sources': [len(s) for s in self.sources],
            'n_in_sinks': [len(s) for s in self.sinks],
            'sw': self._sw,
            'exception': self._exception,
            'all_exceptions': self._except._groups,
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
        e.g. `[Block_123412341 24,580 buffers, 1,230 x/s]`
        '''
        n = self.processed
        total_time = self._sw.elapsed()
        n_src = [len(s) for s in self.sources]
        n_snk = [len(s) for s in self.sinks]
        return f'[{self.name} {n:,} buffers, {n / total_time:,.2f}x/s sources={n_src}, sinks={n_snk}]'

    def stats_summary(self):
        stats = self.stats()
        return text.block_text(
            # block title
            'Stats for {summary_banner}',
            # any exception, if one was raised.
            text.red('({}) {}'.format(type(self._exception).__name__, self._exception))
            if self._exception else None,
            # basic stats
            'Processed {processed} buffers in {total_time:.2f} sec. ({speed:.2f} x/s)',
            'Dropped: {dropped}  Skipped: {skipped}  Left in Queue: in={n_in_sources} out={n_in_sinks}',
            # timing info
            self._sw, ch=text.blue('*')).format(
                summary_banner=text.red(self) if self.error else text.green(self),
                **stats)

    def print_stats(self):
        print(self.stats_summary())


def prepare_output(outputs, input_meta=None, expected_length=None):
    '''Take the inputs from block.process and prepare to be passed to block.sinks.'''
    if not outputs:
        return (), {}

    bufs, meta = None, None
    if isinstance(outputs, tuple):
        if len(outputs) == 2:
            bufs, meta = outputs
    elif isinstance(outputs, (Meta, dict)):
        meta = outputs

    bufs = list(bufs) if bufs else []

    if expected_length:  # pad outputs with blank values
        bufs.extend((reip.BLANK,) * max(0, expected_length - len(bufs)))

    if input_meta:  # merge meta as a new layer
        meta = Meta(meta, input_meta)
    return bufs, meta or Meta()
