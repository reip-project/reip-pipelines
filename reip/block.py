import time
import threading
import traceback

import reip
from reip.stores import Producer
from reip.util import text, Meta

__all__ = ['Block']


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

    def __init__(self, n_source=1, n_sink=1, queue=1000, blocking=False,
                 max_rate=None, max_processed=None, graph=None, name=None, **kw):
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.context_id = reip.Task.register_instance(self, graph)

        # sources and sinks
        # by default, a block takes a variable number of sources.
        # If a block has a fixed number of sources, you can specify that
        # and it will throw an exception when spawning if the number of
        # sources does not match.
        self.n_expected_sources = n_source
        self.sources = [None] * (n_source or 0)
        # TODO: should we have n_sink=None, signify, n_sink=n_source ?
        self.sinks = [
            Producer(queue, context_id=self.context_id)
            for _ in range(n_sink or 0)
        ]

        self.max_rate = max_rate
        self.max_processed = max_processed
        self._put_blocking = blocking
        # signals
        self._reset_state()
        # block timer
        self._sw = reip.util.Stopwatch(str(self))
        self.extra_kw = kw

        self.log = reip.util.logging.getLogger(self)

    def _reset_state(self):
        # state
        self.ready = False
        self.error = False  # QUESTION: can we combine error + _exception?
        self._exception = None
        self.done = False
        # stats
        self.processed = 0
        # self._sw.reset()

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
            else:
                sinks = reip.util.as_list(other)

            if sinks:
                # truncate if necessary
                if self.n_expected_sources:
                    sinks = sinks[:min(self.n_expected_sources, j + len(sinks))]

                # make sure the list is long enough
                self.sources = reip.util.resize_list(
                    self.sources, j + len(sinks), None)

                # create and add the source
                for j, sink in enumerate(sinks, j):
                    self.sources[j] = sink.gen_source(
                        context_id=self.context_id, **kw)
                j += 1  # need to increment cursor so we don't repeat last index

                if (self.n_expected_sources and
                        len(self.sources) >= self.n_expected_sources):
                    break

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

    # User Interface

    def init(self):
        '''Initialize the block.'''

    def process(self, *xs, meta=None):
        '''Process data.'''
        return xs, meta

    def finish(self):
        '''Cleanup.'''

    # main process loop

    def _main(self, *a, **kw):
        '''The main thread target function. Handles uncaught exceptions and
        generic Block context management.'''
        try:
            # profiler = pyinstrument.Profiler()
            # profiler.start()
            self.log.debug(text.blue('Starting...'))
            time.sleep(self._delay)
            with self._sw():
                self._run(self._init_stream(*a, **kw))
        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
        finally:
            self.print_stats()
            # profiler.stop()
            # print(profiler.output_text(unicode=True, color=True))
            self.log.info(text.green('Done.'))

    def _run(self, stream):
        '''The abstract block logic. This is meant to be overrideable in case
        someone needs to modify the logic organization.'''
        try:
            # initialize the block
            self._do_init()
            # iterate over the input data gathered from the sources
            for buffers, meta in stream:
                # process each input batch
                outputs = self._do_process(*buffers, meta=meta)
                # send each output batch to the sinks
                self._do_sinks(outputs, meta)
        except Exception as e:
            self._handle_exception(e)
        finally:
            # finish up and shut down block
            self._do_finish()

    def _do_init(self):
        '''Initialize the block. Handles block timing and any logging.'''
        # create a new streamer that reads data from sources
        with self._sw('init'):
            self.init()
        self.ready = True
        self.log.info(text.green('Ready.'))

    def _init_stream(self, duration=None):
        '''Initialize the source stream.

        NOTE: this should set self._stream to be the reip.Stream object so that
        we can call Stream methods to pause, terminate, etc.
        It can return a wrapped iterable which will be used to iterate inside
        the run function, e.g. wrap it with a timer, or additional formatting.
        '''
        # create a stream from sources with a custom control loop
        self._stream = reip.Stream.from_block_sources(
            self, duration=duration, name=self.name)
        self._stream.open()
        # wrap stream in a timer
        return self._sw.iter(self._stream, 'source')

    def _do_process(self, *buffers, meta=None):
        '''Process buffers. Handles block timing and any logging.'''
        with self._sw('process'):
            outputs = self.process(*buffers, meta=meta)
        return outputs

    def _do_finish(self):
        '''Cleanup block. Handles block timing and any logging.'''
        self.log.debug(text.yellow('Finishing...'))
        self._stream.close()  # may be redundant
        # run block finish
        with self._sw('finish'):
            self.finish()
        # propagate stream signals to sinks e.g. CLOSE
        # this is run when:
        #   - the block sends reip.CLOSE, reip.TERMINATE as a signal from process.
        #     (if you only want to close the current block and not downstream ones,
        #      just call self.close()/self.terminate() directly)
        #   - a stream finishes running e.g. when you set a block run duration.
        if self._stream.signal is not None:
            self.emit_signal(self._stream.signal)
        self.done = True

    def _do_sinks(self, outputs, meta_in=None):
        '''Send the outputs to the sink.'''
        with self._sw('sink'):
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
                if any(any(t.check(o) for t in reip.SOURCE_TOKENS) for o in outputs):
                    # check signal values
                    if len(outputs) > len(self.sources):
                        raise RuntimeError(
                            f'Too many signals for sources in {self}. '
                            f'Got {len(outputs)}, expected a maximum '
                            f'of {len(self.sources)}.')
                    # process signals
                    for s, out in zip(self._stream.sources, outputs):
                        if out == reip.RETRY:
                            pass
                        else:
                            s.next()
                    return

                # convert outputs to a consistent format
                outs, meta = prepare_output(outputs, input_meta=meta_in)
                # increment sources
                self._stream.next()

                # pass to sinks
                self.processed += 1
                for sink, out in zip(self.sinks, outs):
                    if sink is not None:
                        sink.put((out, meta), self._put_blocking)
                if self.max_processed and self.processed >= self.max_processed:
                    self.close(propagate=True)

    def _handle_exception(self, exc):
        self._exception = exc
        self.error = True
        self.log.exception(exc)
        self.terminate()

    def emit_signal(self, signal, block=True, meta=None):
        '''Emit a signal to all sinks.'''
        self.log.debug(text.yellow(text.l_('sending', signal)))
        # print(text.yellow(text.l_(self, 'sending', signal)))
        for sink in self.sinks:
            if sink is not None:
                sink.put((signal, meta or {}), block=block)
    # Thread management

    def spawn(self, wait=True):
        '''Spawn the block thread'''
        # print(text.l_(text.blue('Spawning'), self, '...'))
        # self.log.debug(text.blue('Spawning...'))
        # print(self.summary())

        self._check_source_connections()
        # spawn any sinks that need it
        for s in self.sinks:
            if hasattr(s, 'spawn'):
                s.spawn()
        self._reset_state()
        self.resume()
        self._thread = threading.Thread(target=self._main)
        self._thread.daemon = True
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

    def wait_until_ready(self):
        '''Wait until the block is initialized.'''
        while not self.ready and not self.error and not self.done:
            time.sleep(self._delay)

    def join(self, close=True, terminate=False, raise_exc=False, timeout=None):
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
        # self.log.debug(text.blue('Joining'))
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if raise_exc:
            self.raise_exception()

    def raise_exception(self):
        if self._exception is not None:
            raise self._exception

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
            self.emit_signal(reip.CLOSE)

    def terminate(self, propagate=False):
        if self._stream is not None:
            self._stream.terminate()
        if propagate:
            self.emit_signal(reip.TERMINATE)

    # XXX: this is temporary. idk how to elegantly handle this
    @property
    def running(self):
        return self._stream.running if self._stream is not None else False

    @property
    def terminated(self):
        return self._stream.terminated if self._stream is not None else False

    # debug

    def stats(self):
        return {
            'name': self.name,
            'processed': self.processed,
            'dropped': [getattr(sink, "dropped", None) for sink in self.sinks],
            'sw': self._sw,
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
        return f'[{self.name} {n:,} buffers, {n / total_time:,.2f} x/s]'

    def print_stats(self):
        total_time = self._sw.stats()[0] if '' in self._sw._samples else 0
        print(text.block_text(
            # block title
            f'Stats for {text.red(self) if self.error else text.green(self)}',
            # any exception, if one was raised.
            text.red(f'({type(self._exception).__name__}) {self._exception}')
            if self._exception else None,
            # basic stats
            f'Processed {self.processed} buffers in {total_time:.2f} sec. '
            f'({self.processed / total_time if total_time else 0:.2f} x/s)',
            f'Dropped: {[getattr(sink, "dropped", None) for sink in self.sinks]}',
            # timing info
            self._sw, ch=text.blue('*')))


def prepare_output(outputs, input_meta=None, expected_length=None):
    '''Take the inputs from block.process and prepare to be passed to block.sinks.'''

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
