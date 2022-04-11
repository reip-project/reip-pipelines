import time
import threading
import warnings
from contextlib import contextmanager
import remoteobj

import reip
from reip.stores import Producer
from reip.util import text, Meta

'''

'''

__all__ = ['Block']


class _BlockSinkView:
    '''This is so that we can select a subview of a block's sinks. This is similar
    in principal to numpy views. The alternative is to store the state on the original
    object, but that would have unintended consequences if someone tried to create two
    different views from the same block.
    '''
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

    def to(self, *others, squeeze=True, **kw):
        '''Connect this blocks sinks to other blocks' sources.
        
        .. code-block:: python

            InputBlock().to(ProcessBlock())
        '''
        outs = [other(self.items, **kw) for other in others]
        return outs[0] if squeeze and len(outs) == 1 else outs

    def output_stream(self, strategy='all', source_strategy=all, **kw):
        '''Create a Stream iterator which will let you iterate over the
        outputs of a block.'''
        return reip.Stream([s.gen_source(strategy=strategy, **kw) for s in self.items], strategy=source_strategy, **kw)


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
    _delay = 1e-4
    parent_id, task_id = None, None
    started = ready = done = closed = _terminated = False
    processed = 0
    controlling = False
    max_rate = None

    def __init__(self, n_inputs=1, n_outputs=1, queue=100, blocking=False, print_summary=True,
                 max_rate=None, min_interval=None, max_processed=None, graph=None, name=None,
                 source_strategy=all, extra_kw=True, extra_meta=None, log_level=None,
                 handlers=None, modifiers=None, input_modifiers=None, **kw):
        self._except = remoteobj.LocalExcept(raises=True)
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.parent_id, self.task_id = reip.Graph.register_instance(self, graph)
        self._print_summary = print_summary

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
        # handlers are wrapper functions that can do things like catch errors and restart when a block is closing.
        self.handlers = reip.util.as_list(handlers or [])
        # modifiers are functions that can be used to alter the output of the block before they are
        # sent to a sink
        self.modifiers = reip.util.as_list(modifiers or [])
        self.input_modifiers = reip.util.as_list(input_modifiers or [])

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

        self._extra_meta = reip.util.as_list(extra_meta or [])
        if self._extra_meta:
            # this will flatten a list of dicts into a single dict. Since call=False,
            # if there is a list of dictionaries and a function, any dictionaries
            # before the function will be collapsed, and any after will be left.
            # Calling again (without call=False), will evaluate fully and return
            # the a flattened dict.
            self._extra_meta = reip.util.mergedict(self._extra_meta, call=False)

        if extra_kw:
            self.extra_kw = kw
            for key, value in kw.items():
                setattr(self, key, value)
        elif kw:
            raise TypeError('{} received {} unexpected keyword arguments: {}.'.format(
                self, len(kw), set(kw)))

        # block timer
        self._sw = reip.util.Stopwatch(self.name)
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
        # NOTE: if n is -1, no resize will happen
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
        self.closed = False
        self._terminated = False
        # stats
        self.processed = 0
        self.old_processed = 0
        self.old_time = time.time()
        self._sw.reset()
        self._except.clear()

    def __repr__(self):
        return 'Block({}): ({}/{} in, {} out; {} processed) - {}'.format(
            self.name, sum(s is not None for s in self.sources),
            self.n_expected_sources,
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

    def __call__(self, *others, index=0, **kw):
        '''Connect other block sinks to this blocks sources.
        If the blocks have multiple sinks, they will be passed as additional
        inputs.

        .. code-block:: python

            ProcessBlock()(InputBlock())
        '''
        j = next(
            (i for i, s in enumerate(self.sources) if s is None), len(self.sources)
        ) if index == -1 else index
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
        '''Connect this blocks sinks to other blocks' sources.
        
        .. code-block:: python

            InputBlock().to(ProcessBlock())
        '''
        outs = [other(self, **kw) for other in others]
        return outs[0] if squeeze and len(outs) == 1 else outs

    def __or__(self, other):
        '''Connect blocks using Unix pipe syntax.
        
        .. code-block:: python

            InputBlock() | ProcessBlock()
        '''
        return self.to(*reip.util.as_list(other))

    def __ror__(self, other):
        '''Connect blocks using Unix pipe syntax. See :meth:`__or__`'''
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
            self.started = True
            self.closed = False
            self.log.debug(text.blue('Starting...'))
            time.sleep(self._delay)

            with self._sw(), self._except(raises=False):
                # create a stream from sources with a custom control loop
                self._stream = reip.Stream.from_block_sources(
                    self, name=self.name, _sw=self._sw,
                    strategy=self._source_strategy)

                # self.__first_time = True
                # this lets us wrap the block's run function with retry loops, error suppression and
                # whatever else might be useful
                run = reip.util.partial(self.__main_run, _ready_flag=_ready_flag, duration=duration)
                for wrapper in self.handlers[::-1]:
                    run = reip.util.partial(wrapper, self, run)
                run()
        finally:
            try:
                # propagate stream signals to sinks e.g. CLOSE
                if self._stream.signal is not None:
                    self._send_sink_signal(self._stream.signal)
            finally:
                self.done = True
                self.started = False
                self.closed = True
                self.log.debug(text.green('Done.'))


    def __main_run(self, _ready_flag=None, duration=None):
        # # This is to return from a retry loop that doesn't want to close
        # if not self.__first_time and self.closed:
        #     return
        # self.__first_time = False
        try:
            with self._stream:
                self._sw.tick()  # offset time delay due to the reip initialization (e.g. plasma store warm-up)
                # block initialization
                with self._sw('init'): #, self._except('init')
                    self.init()
                self.ready = True
                self.log.debug(text.green('Ready.'))

                if _ready_flag is not None:
                    with self._sw('wait'):
                        _ready_flag.wait()

                # the loop
                loop = reip.util.iters.throttled(
                    reip.util.iters.timed(reip.util.iters.loop(), duration),
                    self.max_rate, delay=self._delay)

                self.old_time = time.time()  # offset self.init() time delay for proper immediate speed calculation

                for _ in self._sw.iter(loop, 'sleep'):
                    inputs = self._stream.get()
                    if inputs is None:
                        break

                    # process each input batch
                    with self._sw('process'): #, self._except('process')
                        buffers, meta = inputs

                        if self._extra_meta:
                            meta.maps += reip.util.flatten(self._extra_meta, call=True, meta=meta)
                        for func in self.input_modifiers:
                            buffers, meta = func(*buffers, meta=meta)
                        outputs = self.process(*buffers, meta=meta)
                        for func in self.modifiers:
                            outputs = func(outputs)

                    # This block of code needs to be here or else self.processed is not counting calls to self.process() function
                    # but buffers generated by current block and thus self.processed will be zero or inacurate in a number of cases:
                    # (i) black hole block that is only consuming data, (ii) data source block that has a buitin buffer bundling/grouping capabilities
                    # We can always add another self.generated counter if we need/want to
                    self.processed += 1
                    # limit the number of blocks
                    if self.max_processed and self.processed >= self.max_processed:
                        self.close(propagate=True)

                    # send each output batch to the sinks
                    with self._sw('sink'):
                        self.__send_to_sinks(outputs, meta)

        except KeyboardInterrupt as e:
            self.log.info(text.yellow('Interrupting'))
            self.log.exception(e)
            # reip.util.print_stack('Interrupted here')
        except Exception as e:
            self.log.exception(e)
            raise
        finally:
            self.ready = False
            # finish up and shut down
            self.log.debug(text.yellow('Finishing...'))
            with self._sw('finish'): # , self._except('finish', raises=False)
                self.finish()

    def __send_to_sinks(self, outputs, meta_in=None):
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
                # See self.__main_run()
                # self.processed += 1
                # # limit the number of blocks
                # if self.max_processed and self.processed >= self.max_processed:
                #     self.close(propagate=True)

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
        try:
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
            self._thread = remoteobj.util.thread(self._main, _ready_flag=_ready_flag, daemon_=True, raises_=False)
            # threading.Thread(target=self._main, kwargs={'_ready_flag': _ready_flag}, daemon=True)
            self._thread.start()

            if wait:
                self.wait_until_ready()
            if self.controlling:
                self.raise_exception()
        finally:
            # thread didn't start ??
            if self._thread is None or not self._thread.is_alive():
                self.done = True

    def _check_source_connections(self):
        '''Check if there are too many sources for this block.'''
        # check for any empty sources
        disconnected = [i for i, s in enumerate(self.sources) if s is None]
        if disconnected:
            raise RuntimeError(f"Sources {disconnected} in {self} not connected.")

        # check for exact source count
        if (self.n_expected_sources is not None and self.n_expected_sources != -1
                and len(self.sources) != self.n_expected_sources):
            raise RuntimeError(
                f'Expected {self.n_expected_sources} sources '
                f'in {self}. Found {len(self.sources)}.')

    def remove_extra_sources(self, n=None):
        n = n or self.n_expected_sources
        if n is not None and n != -1:
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
        if self._print_summary:  # print now or part of the stats will be lost if the block is used inside of Task
            print(self.stats_summary())

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
        self.closed = True
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

    # @property
    # def closed(self):
    #     return self._stream.should_wait if self._stream is not None else True

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
        e.g. `Block_123    +   2 buffers (2.09 x/s),   9 total (1.47 x/s avg),  sources=[1], sinks=[0]`
        '''
        n = self.processed
        total_time = self._sw.elapsed()
        init_time = self._sw.stats("init").sum if 'init' in self._sw else 0
        speed_avg = n / (total_time - init_time)

        n_new = n - self.old_processed
        speed_now = n_new / (time.time() - self.old_time)
        self.old_processed, self.old_time = n, time.time()

        n_src = [len(s) for s in self.sources]
        n_snk = [len(s) for s in self.sinks]

        return f'{self.name}\t + {n_new:3} buffers ({speed_now:,.2f} x/s), {n:5} total ({speed_avg:,.2f} x/s avg),  sources={n_src}, sinks={n_snk}'

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

    # def print_stats(self):
    #     print(self.stats_summary())


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
        if isinstance(meta, Meta):  # only the user did not wish to override it
            meta = Meta(meta, input_meta)
        else:
            meta = Meta(meta)
    return bufs, meta or Meta()
