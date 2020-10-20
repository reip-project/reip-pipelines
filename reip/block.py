import time
import threading
import traceback
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
        n_source (int, or None): the number of sources to expect. If None,
            it will accept a variable number of sources.
        n_sink (int): the number of sinks to expect.
             - If `n_sink=0`, then there will be a single sink, that outputs no
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
             - If `n_sink=None`, then the block will have no sinks.

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
    ready = done = False
    processed = 0

    def __init__(self, n_source=1, n_sink=1, queue=1000, blocking=False,
                 max_rate=None, max_processed=None, graph=None, name=None, **kw):
        self._except = remoteobj.LocalExcept()
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.parent_id, self.task_id = reip.Graph.register_instance(self, graph)

        # sources and sinks
        # by default, a block takes a variable number of sources.
        # If a block has a fixed number of sources, you can specify that
        # and it will throw an exception when spawning if the number of
        # sources does not match.
        self.n_expected_sources = n_source
        self.sources = [None] * (n_source or 0)
        # TODO: should we have n_sink=None, signify, n_sink=n_source ?
        self.sinks = [
            Producer(queue, task_id=self.task_id)
            for _ in range(n_sink or 0)
        ]

        self.max_rate = max_rate
        self.max_processed = max_processed
        self._put_blocking = blocking
        self.extra_kw = kw
        # block timer
        self._sw = reip.util.Stopwatch(str(self))
        self.log = reip.util.logging.getLogger(self)
        # signals
        self._reset_state()

    def _reset_state(self):
        # state
        self.ready = False
        self.done = False
        # stats
        self.processed = 0
        self._sw.reset()
        self._except.clear()

    def __repr__(self):
        state = (
            (type(self._exception).__name__
             if self._exception is not None else 'error') if self.error else
            ('terminated' if self.terminated else 'done') if self.done else
            ('running' if self.running else 'paused') if self.ready else
            '--'  # ??
        )  # add "uptime 35.4s"

        return '[Block({}): ({}/{} in, {} out; {} processed) - {}]'.format(
            self.name, sum(s is not None for s in self.sources),
            '?' if self.n_expected_sources is None else self.n_expected_sources,
            len(self.sinks), self.processed,
            state)

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
                self.sources = reip.util.resize_list(
                    self.sources, j + len(sinks), None)

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

    def _main(self, _ready_flag=None, **kw):
        '''The main thread target function. Handles uncaught exceptions and
        generic Block context management.'''
        with self._except:
            try:
                # profiler = pyinstrument.Profiler()
                # profiler.start()
                self.log.debug(text.blue('Starting...'))
                time.sleep(self._delay)
                with self._sw():
                    # create a stream from sources with a custom control loop
                    self._stream = reip.Stream.from_block_sources(self, name=self.name, _sw=self._sw)
                    with self._stream:
                        # block initialization
                        with self._sw('init'), self._except('init'):
                            self.init()
                        self.ready = True
                        self.log.info(text.green('Ready.'))
                        if _ready_flag is not None:
                            _ready_flag.wait()

                        for _ in self._stream.get_loop(**kw):
                            with self._sw('source'):
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

                self.print_stats()
                # profiler.stop()
                # print(profiler.output_text(unicode=True, color=True))
                self.log.info(text.green('Done.'))
                self.done = True

    def _send_to_sinks(self, outputs, meta_in=None):
        '''Send the outputs to the sink.'''
        # retry all sources
        if outputs == reip.RETRY:
            pass
        elif outputs == reip.CLOSE:
            self.close(propagate=True)
        elif outputs == reip.TERMINATE:
            self.terminate(propagate=True)
        # increment sources but don't have any outputs to send
        elif outputs is None:
            self._stream.next()
        # increment sources and send outputs
        else:
            # detect signals meant for the source
            if self._stream.check_signals(outputs):
                return

            # increment sources
            self._stream.next()
            self.processed += 1

            # convert outputs to a consistent format
            outs, meta = prepare_output(outputs, input_meta=meta_in)
            # pass to sinks
            for sink, out in zip(self.sinks, outs):
                if sink is not None:
                    sink.put((out, meta), self._put_blocking)
            # limit the number of blocks
            if self.max_processed and self.processed >= self.max_processed:
                self.close(propagate=True)

    def _send_sink_signal(self, signal, block=True, meta=None):
        '''Emit a signal to all sinks.'''
        self.log.debug(text.yellow(text.l_('sending', signal)))
        for sink in self.sinks:
            if sink is not None:
                sink.put((signal, meta or {}), block=block)

    # Thread management

    def spawn(self, wait=True, _ready_flag=None):
        '''Spawn the block thread'''
        self.controlling = _ready_flag is None
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
        return self._except._last

    @property
    def all_exceptions(self):
        return self._except.all()

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
        return self._stream.terminated if self._stream is not None else False

    # debug

    def stats(self):
        total_time = self._sw.stats()[0] if '' in self._sw._samples else 0
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

    def print_stats(self):
        total_time = self._sw.stats()[0] if '' in self._sw._samples else 0
        speed = self.processed / total_time if total_time else 0
        dropped = [getattr(s, "dropped", None) for s in self.sinks]
        skipped = [getattr(s, "skipped", None) for s in self.sources]
        n_src = [len(s) for s in self.sources]
        n_snk = [len(s) for s in self.sinks]
        print(text.block_text(
            # block title
            f'Stats for {text.red(self) if self.error else text.green(self)}',
            # any exception, if one was raised.
            text.red(f'({type(self._exception).__name__}) {self._exception}')
            if self._exception else None,
            # basic stats
            f'Processed {self.processed} buffers in {total_time:.2f} sec. '
            f'({speed:.2f} x/s)',
            f'Dropped: {dropped}  Skipped: {skipped}',
            f'Left in Queue: sources={n_src} sinks={n_snk}',
            # timing info
            self._sw, ch=text.blue('*')))


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
