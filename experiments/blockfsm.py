'''This is where I'm experimenting with state machine mechanics in the context of a block.

I'm starting with a striped down version that doesn't handle connections or anything atm.
'''
import time
import reip
from contextlib import contextmanager
import remoteobj
from reip.util import text


class ReipControl(BaseException):
    pass

class WorkerExit(ReipControl):
    pass



class _BlockConnectable:
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
        self.idx = idx

    @property
    def sinks(self):
        return reip.util.as_list(self.block.sinks[self.idx])

    def __call__(self, *a, **kw):
        return self.block(*a, index=self.idx, **kw)

    def __iter__(self):
        yield from self.sinks


def get_indices(i, n):
    i = slice(i, None) if isinstance(i, int) else slice(n) if i is None else i
    if isinstance(i, slice):
        return list(range(i.start or 0, i.stop or n, i.step or 1))
    return i


class Block(_BlockConnectable):
    USE_META_CLASS = True
    _delay = 1e-4
    _wait_delay = 1e-2
    _agent = None
    processed = generated = 0
    n_inputs = n_outputs = 1

    def __init__(self, 
                 n_inputs=None, n_outputs=None,
                 max_rate=None, should_process=all, log_level='debug', queue_length=100,
                 extra_meta=None, max_processed=None, max_generated=None, extra_kw=False,
                 graph=None, name=None, **kw):
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
                    'closing': {},
                },
                'needs_reconfigure': {},
            },
            'done': {None: {'terminated': {}}},
            # unlinked states
            None: {'_controlling': {}}
        })

        self.__source_process_condition = should_process
        self._extra_meta = extra_meta
        self.__max_processed = max_processed
        self.__max_generated = max_generated

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

        for k in reip.util.clsattrdiff(Block, self.__class__):
            if k in kw:
                setattr(self, k, kw.pop(k))

        self.extra_kw = None
        if extra_kw:
            self.extra_kw = kw
        elif kw:
            raise TypeError("{} got unexpected arguments: {}".format(self, ', '.join(kw)))

    def __str__(self):
        return '[B({})[{}/{}]{}]'.format(self.name, len(self.sources), len(self.sinks), self.state)

    def status(self):
        return str(self)

    # compat

    @property
    def _thread(self):
        return self._agent

    @property
    def ready(self):
        return bool(self.state.ready)

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
        return self._except.caught

    def raise_exception(self):
        self.check_agent_exception()

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

    def __call__(self, *others, index=None, **kw):
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

        # get the corresponding source indices for matching source to sink
        n_inputs = self.n_inputs
        if n_inputs < 0:
            n_inputs = len(sinks)
            if isinstance(index, slice):
                n_inputs = index.start + n_inputs * index.step

        # create and add the source
        for sink, i_src in zip(sinks, get_indices(index, n_inputs)):
            # make sure the list is long enough
            while len(self.sources) <= i_src:
                self.sources.append(None)
            self.sources[i_src] = sink.gen_source(task_id=self.task_id, **kw)
        return self

    # Control Interface

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
            if self.state.done:
                return True

    def spawn(self, wait=True, *, _controlling=False, _ready_flag=None, _spawn_flag=None):
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
        disconnected = [i for i, s in enumerate(self.sources) if s is None]
        if disconnected:
            raise RuntimeError(f"Sources {disconnected} in {self} not connected.")

        # check for exact source count
        if (self.n_inputs >= 0 and len(self.sources) != self.n_inputs):
            raise RuntimeError(
                f'Expected {self.n_inputs} sources '
                f'in {self}. Found {len(self.sources)}.')

    def check_agent_exception(self):
        self._except.raise_any()

    # internal state lifecycle

    def __reset_state(self):
        self.state.reset()
        self.processed = 0
        self.generated = 0
        self.__source_signals = [None] * len(self.sources)

    def __agentless_spawn(self):
        try:
            self.__reset_state()
            self.__agent_main()
        finally:
            pass

    def __agent_main(self, *, _spawn_flag=None, _ready_flag=None):
        if _spawn_flag:
            _spawn_flag.wait()
        try:
            with self._except, self._sw(), self.state.spawned:  # , self._except(raises=False)
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
        self.state.configured()

    def __run_configured(self):
        try:
            with self.state.initializing:
                self.init()

            with self.state.ready, self.__throttler as throttle:
                while self.state.configured:
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
                    self.state.waiting = False

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
            with self.state.closing:
                self.finish()


    def __read_sources(self):
        inputs = [s.get_nowait() for s in self.sources]
        # check inputs
        recv_close = False
        for data, source in zip(inputs, self.sources):
            if data is None:
                continue

            x, meta = data
            if reip.CLOSE.check(x):  # XXX: how to handle - wait for all to close?
                source.next()
                self.close()
                recv_close = True
            if reip.TERMINATE.check(x):
                source.next()
                self.terminate()
                recv_close = True
        if recv_close:
            return

        buffers, meta = prepare_input(inputs, Block.USE_META_CLASS)
        return buffers, meta

    def __process_buffer(self, buffers, meta):
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
        for outs in (outputs if reip.util.is_iter(outputs) else iter((outputs,))):
            if outs is None:  # next
                continue

            # convert outputs to a consistent format
            outs = prepare_output(outs, input_meta, as_meta=Block.USE_META_CLASS)
            # pass to sinks
            for sink, (out, meta) in zip(self.sinks, outs):
                if sink is not None:
                    sink.put((out, meta))

            # count the number of buffers generated
            self.generated += 1
            # limit the number of buffers
            if self.__max_generated and self.generated >= self.__max_generated:
                self.close(propagate=True)

        for i, src in enumerate(self.sources):
            if self.__source_signals[i] is reip.RETRY:
                pass
            else:
                src.next()
            self.__source_signals[i] = None

    def source_signal(self, signals):
        if isinstance(signals, (reip.Token, str)):
            signals = [signals] * len(self.sources)
        elif len(signals) > len(self.sources):
            raise RuntimeError('Too many signals for sources. Got {}, expected ≤{}.'.format(
                len(signals), len(self.sources)))
        for i, (_, sig) in enumerate(zip(self.__source_signals, signals)):
            self.__source_signals[i] = sig

    def __send_sink_signal(self, signal, block=True, meta=None):
        '''Emit a signal to all sinks.'''
        for sink in self.sinks:
            if sink is not None:
                sink.put((signal, meta or {}), block=block)



def prepare_input(inputs, as_meta=True):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, metas = tuple(zip(*([buf if buf is not None else (None, {}) for buf in inputs]))) or ((), ())

    if as_meta:
        metas = reip.Meta(inputs=metas)
    else:
        if len(metas) == 1:
            metas = metas[0]
    return bufs, metas


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
    for x, meta in outputs:
        if meta is None:
            meta = reip.util.Meta() if as_meta else {}
        if as_meta and not isinstance(meta, reip.util.Meta):
            meta = reip.util.Meta(meta, input_meta.inputs)
        outs.append((x, meta))
    return outs




class Throttler:
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


class ExceptionTracker:
    def __init__(self):
        self.caught = []
        self.types = {}

    def __str__(self):
        return '<ExceptCatch groups={} n={} types={}>'.format(
            set(self.types), len(self.caught), {type(e).__name__ for e in self.caught})

    def __call__(self, name=None):
        try:  # only created once
            return self.types[name]
        except KeyError:  
            # only catch exceptions that reach the top
            track = self.caught if name is None else False
            catcher = self.types[name] = _ExceptCatch(name, track)
            return catcher

    def __enter__(self):
        return self().__enter__()

    def __exit__(self, *a):
        return self().__exit__(*a)

    def raise_any(self):
        for e in self.caught:
            raise e

class _ExceptCatch:
    def __init__(self, name, track=False):
        self.name = name
        self.track = [] if track is True else track

    def __str__(self):
        return '<ExceptCatch[{}]>'.format(self.name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_value and isinstance(exc_value, Exception):
            exc_value._exception_tracking_name_ = self.name
            if self.track is not False:
                self.track.append(exc_value)

# # https://github.com/python/cpython/blob/5acc1b5f0b62eef3258e4bc31eba3b9c659108c9/Lib/concurrent/futures/process.py#L127
# class _RemoteTraceback(Exception):
#     def __init__(self, tb):
#         self.tb = tb
#     def __str__(self):
#         return self.tb

# class RemoteException:
#     '''A wrapper for exceptions that will preserve their tracebacks
#     when pickling. Once unpickled, you will have the original exception
#     with __cause__ set to the formatted traceback.'''
#     def __init__(self, exc):
#         self.exc = exc
#         self.tb = '\n"""\n{}"""'.format(''.join(
#             traceback.format_exception(type(exc), exc, exc.__traceback__)
#         ))
#     def __reduce__(self):
#         return _rebuild_exc, (self.exc, self.tb)

# def _rebuild_exc(exc, tb):
#     exc.__cause__ = _RemoteTraceback(tb)
#     return exc



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
