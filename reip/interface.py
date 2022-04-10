import time
import reip


def skip_strategy(source):
    while not source.empty() and source._skip_id < source.skip:
        # source._get()
        source.next()  # discard the buffer
        source._skip_id += 1
        source.skipped += 1

    if source._skip_id == source.skip and not source.empty():
        buffer = source._get()
        source._skip_id = 0  # might not process this buffer in multi_source block
        return buffer


def latest_strategy(source):
    while not source.last():
        # source._get()
        source.next()  # discard the buffer
        source.skipped += 1
    return source._get()


def all_strategy(source):
    if not source.empty():
        return source._get()


class Sink:
    '''An abstract interface representing a place to put data.
    
    Essentially, a put-only queue.
    '''
    def __init__(self):
        self.dropped = 0
        self._full_delay = 1e-6

    def spawn(self):
        '''An optional method that allows a sink to perform initialization.'''
        pass

    def join(self):
        '''An optional method that allows a sink to perform cleanup.'''
        pass

    def __len__(self):
        '''How many elements are in the queue.'''
        raise NotImplementedError

    def full(self):
        '''Is the queue full?'''
        raise NotImplementedError

    def _put(self, buffer):
        '''The overrideable method to put items in the queue.'''
        raise NotImplementedError

    def wait(self, timeout=None):
        '''Wait until the queue has space for another element.'''
        t0 = time.time()
        while self.full():
            time.sleep(self._full_delay)
            if timeout and time.time() - t0 > timeout:
                return None  # QUESTION: TimeoutError instead?

    def put(self, buffer, block=True, timeout=None):
        '''Put an element in the sink.'''
        if block:
            self.wait(timeout)
        return self.put_nowait(buffer)

    def put_nowait(self, buffer):
        '''Put an element in the sink, dropping the value if the queue is full.'''
        if self.full():
            self.dropped += 1
        else:
            self._put(buffer)

    def gen_source(self, **kw):
        raise NotImplementedError


class Source:
    '''An abstract interface representing a place to get data.
    
    Essentially, a get-only queue.
    '''
    # TODO: make it easier for someone to register a new strategy
    #       e.g.:
    #         @Source.register
    #         def SkipStochastic(source): ...
    All = 'all'
    Latest = 'latest'
    Skip = 'skip'

    strategies = {
        All: all_strategy,
        Latest: latest_strategy,
        Skip: skip_strategy,
    }

    _strategy = All

    def __init__(self, strategy=All, skip=0, default=None):
        self.strategy = strategy
        self.skip = skip
        self._skip_id = 0
        self.skipped = 0
        self._empty_delay = 1e-6
        self._default = reip.util.as_func(default) if default is not None else default

    @property
    def strategy(self):
        return self._strategy

    @strategy.setter
    def strategy(self, strategy):
        if strategy not in self.strategies:
            raise ValueError("Unknown strategy '{}'".format(strategy))

        self._strategy = strategy
        self._strategy_get = self.strategies[strategy]

    def __len__(self):
        '''How many elements are in the Source queue.'''
        raise NotImplementedError

    def empty(self):
        '''Is the Source queue empty?'''
        return not len(self) and self._default is None

    def last(self):
        '''Returns True if there is only one element left.'''
        ln = len(self)
        return ln == 1 or (not ln and self._default is not None)

    def next(self):
        raise NotImplementedError

    def _get(self):
        raise NotImplementedError

    def wait(self, timeout=None):
        '''Wait until an element is ready.'''
        t0 = time.time()
        while self.empty():
            time.sleep(self._empty_delay)
            if timeout and time.time() - t0 > timeout:
                return None  # QUESTION: TimeoutError instead?

    def get(self, block=True, timeout=None):
        '''Get the next element in the queue.'''
        if block:
            self.wait(timeout)
        return self.get_nowait()

    def get_nowait(self):
        '''Get the next element in the queue, returning None if no value is available.'''
        if len(self) == 0:
            if self._default is not None:
                return self._default()
            return None
        return self._strategy_get(self)
