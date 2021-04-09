import time
import reip
import remoteobj
from reip.util import text


class ReipControl(BaseException):
    pass

class BlockExit(ReipControl):
    pass



class Block:
    USE_META_CLASS = True
    _delay = 1e-4
    processed = generated = 0

    def __init__(self, max_rate=None, should_process=all, log_level='debug', 
                 extra_meta=None, max_processed=None, max_generated=None, name=None):
        self.name = reip.auto_name(self, name=name)
        self.state = reip.util.states.States({
            'spawned': {
                'configured': {
                    'initializing': {},
                    'ready': {
                        'waiting': {},
                        'processing': {},
                        'paused': {}
                    },
                    'closing': {},
                },
                'needs_reconfigure': {},
            },
            'done': {
                'terminated': {},
            },
        })
        self.throttler = Throttler(max_rate)
        self._should_process = should_process
        self._extra_meta = extra_meta
        self.max_processed = max_processed
        self.max_generated = max_generated

        self._except = remoteobj.LocalExcept(raises=True)
        self._sw = reip.util.Stopwatch(self.name)
        self.log = reip.util.logging.getLogger(self, level=log_level)

        self.sources = []
        self.sinks = []

    def short_str(self):
        return '[B({})[{}/{}]{}]'.format(self.name, len(self.sources), len(self.sinks), self.state)

    def __str__(self):
        return self.short_str()


    # User Interface

    def init(self):
        '''Initialize the block.'''

    def sources_available(self):
        '''Check the sources to determine if we should call process.'''
        # NOTE: this serves the same purpose as `_should_process` but is easy for subclassing
        return not self.sources or self._should_process(
            not s.empty() for s in self.sources)

    def process(self, *xs, meta=None):
        '''Process data.'''
        return xs, meta

    def finish(self):
        '''Cleanup.'''



    def __reset_state(self):
        self.state.reset()
        self.processed = 0
        self.generated = 0

    def __spawned(self):
        try:
            self.__reset_state()
            self.__thread_main()
        finally:
            pass

    def __thread_main(self):
        try:
            with self._sw(), self.state.spawned:  # , self._except(raises=False)
                try:
                    while self.state.spawned:
                        self.log.info(self.state)
                        if not self.state.configured:
                            self.__reconfigure()
                        self.__run()
                    
                except BlockExit:
                    pass
        finally:
            self.state.configured.off()

    def __reconfigure(self):
        self.state.configured()

    def __run(self):
        try:
            with self.state.initializing:
                self.init()

            with self.state.ready, self.throttler as throttle:
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
                    self.state.waiting.off()

                    # good to go!
                    with self.state.processing:
                        # get inputs
                        with self._sw('source'):
                            inputs = self.__read_sources()
                            if not self.state.processing:
                                break
                            buffers, meta = inputs

                        # process each input batch
                        with self._sw('process'), self._except('process'): #
                            outputs = self.__process_buffer(buffers, meta)

                        # send each output batch to the sinks
                        with self._sw('sink'):
                            self.__send_to_sinks(outputs, meta)

        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
        finally:
            with self.state.closing:
                self.finish()


    def __read_sources(self):
        inputs = [s.get_nowait() for s in self.sources]
        # check inputs
        recv_close = False
        for inp, source in zip(inputs, self.sources):
            for data in inputs:
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
                    return
        if recv_close:
            return

        buffers, meta = prepare_input(inputs, self._extra_meta, Block.USE_META_CLASS)  # TODO: put in proper config
        return buffers, meta

    def __process_buffer(self, buffers, meta):
        # process and get outputs
        outputs = self.process(*buffers, meta=meta)

        # count the number of buffers received and processed
        self.processed += 1
        # limit the number of buffers
        if self.max_processed and self.processed >= self.max_processed:
            self.close(propagate=True)
        return outputs

    def __send_to_sinks(self, outputs, input_meta):
        '''Send the outputs to the sink.'''
        source_signals = [None]*len(self.sources)
        # 
        outputs = outputs if reip.util.is_iter(outputs) else iter((outputs,))

        for outs in outputs:
            if outs == reip.RETRY:
                source_signals = [reip.RETRY]*len(self.sources)
            elif outs == reip.CLOSE:
                self.close()
                break
            elif outs == reip.TERMINATE:
                self.terminate()
                break
            # increment sources but don't have any outputs to send
            elif outs is None:
                pass
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
                outs = prepare_output(outs, input_meta, as_meta=Block.USE_META_CLASS)
                # pass to sinks
                for sink, (out, meta) in zip(self.sinks, outs):
                    if sink is not None:
                        sink.put((out, meta), self._put_blocking)

                # count the number of buffers generated
                self.generated += 1
                # limit the number of buffers
                if self.max_generated and self.generated >= self.max_generated:
                    self.close(propagate=True)

        for src, sig in zip(self.sources, source_signals):
            if sig is reip.RETRY:
                pass
            else:
                src.next()

    def __send_sink_signal(self, signal, block=True, meta=None):
        '''Emit a signal to all sinks.'''
        for sink in self.sinks:
            if sink is not None:
                sink.put((signal, meta or {}), block=block)

    def close(self, propagate=True):
        self.state.done.request()
        if propagate:
            self.__send_sink_signal(reip.CLOSE)

    def terminate(self, propagate=True):
        self.state.done.request()
        if propagate:
            self.__send_sink_signal(reip.TERMINATE)





def prepare_input(inputs, extra_meta=None, as_meta=True):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, metas = tuple(zip(*([buf if buf is not None else (None, {}) for buf in inputs]))) or ((), ())

    if as_meta:
        metas = reip.Meta(inputs=metas)
        if extra_meta is not None:
            metas.extend(reip.util.flatten(extra_meta, call=True, meta=metas))
    else:
        metas = metas or {}
        if len(metas) == 1:
            metas = metas[0]
    return bufs, metas


def prepare_output(outputs, input_meta=None, expected_length=None, as_meta=True):
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

    if meta is None:
        meta = Meta() if as_meta else {}
    if as_meta and not isinstance(meta, Meta):
        meta = Meta(meta, input_meta.inputs)
    return bufs, meta




class Throttler:
    __MAX_RATE_CHUNK = 0.4

    def __init__(self, max_rate=None):
        self.max_rate = None

    def __enter__(self):
        self.t_last = time.time()
        self.sleep_amt = 0
        return self
    
    def __exit__(self, *a):
        pass

    def __call__(self):
        # NOTE: sleep in chunks so that if we have a really high
        #       interval (e.g. run once per hour), then we don't
        #       have to wait an hour to shut down
        if self.max_rate:
            # restart the throttle counter
            sleep_amt = self.sleep_amt
            if not self.sleep_amt:
                ti = time.time()
                sleep_amt = self.sleep_amt = max(0, self.max_rate - (ti - self.t_last))
                self.t_last = ti
            # sleep for the next chunk
            sleep_amt_prev, sleep_amt = sleep_amt, max(0, sleep_amt - self.__MAX_RATE_CHUNK)
            dt = sleep_amt_prev - sleep_amt
            if dt:
                time.sleep(dt)
            if self.sleep_amt:  # return True, will notify that we should keep waiting
                return True
        return False


class MyBlock(Block):
    def init(self):
        self.i = 0

    def process(self, meta):
        self.i += 1
        self.log.info(self.i)
        if self.i > 10:
            # raise ValueError
            self.close()


if __name__ == '__main__':
    block = MyBlock(max_rate=1, max_processed=15)
    block.state_changes = 0
    @block.state.add_callback
    def log_changes(state, value):
        block.state_changes += 1
        if block.state_changes > 100:
            raise Exception('exceeded 100 state changes.')
        if state == 'done':
            for name, state, in block.state._states.items():
                print(state, state.potential)
        if state == 'done' and value == False:
            reip.util.print_stack()
            1/0
        if state == 'terminated' and value == False:
            reip.util.print_stack()
            1/0
        # if not block.state.ready:
        block.log.info('{} - changed to {}'.format(state, value))
    print(block)

    block._Block__spawned()

