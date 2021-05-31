import queue
import time
import remoteobj
import multiprocessing as mp
import reip
try:
    from reip.util.meta2 import Meta
except ImportError:
    from reip.util.meta import Meta
import remoteobj
remoteobj.excs.tblib = None



class BlockExit(SystemExit):
    pass



_NAMESPACES_IDX = {}
def auto_name(block, *attrs, name=None, ns=None, leading=2):
    '''Generate an auto-incrementing name.'''
    # create a name from the block attributes
    name = name or block.__class__.__name__.lower()
    name = name + ''.join('_'+str(x) for x in attrs)
    # get the count, based on some namespace. add count to name if above 1
    namespace = _NAMESPACES_IDX[ns] = _NAMESPACES_IDX.get(ns) or {}
    count = namespace[name] = namespace.get(name, -1) + 1
    return '{}-{:0{leading}.0f}'.format(name, count, leading=leading) if count else name

def aslist(x):
    return x if isinstance(x, list) else [] if x is None else [x]


def run(worker, duration=None):
    try:
        t0 = time.time()
        worker.init()
        while worker.running:
            if duration and time.time() - t0 >= duration:
                worker.log.info('finished duration')
                break
            worker.poll()
            time.sleep(worker._delay)
    except BlockExit:
        worker.log.info('Exiting...')
    except KeyboardInterrupt:
        worker.log.warning('Interrupting...')
    finally:
        worker.finish()


class _QMix:  # patch class for basic queue objects to make them work like reip queues
    _qstr = 'Q'
    def __repr__(self):
        return '{}({}/{})'.format(self._qstr, len(self), self.maxsize)
    def __len__(self):
        return self.qsize()

    def get(self, block=False, timeout=None):
        try:
            return super().get(block, timeout)
        except queue.Empty:
            if block:
                raise
            return None

class Queue(_QMix, queue.Queue):  # patched queue class
    pass

def mpQueue(*a, **kw):  # patched multiprocessing queue - need to use function because of internal mp context wrappers
    q = mp.Queue(*a, **kw)
    cls = q.__class__
    q.__class__ = type('mpQueue', (_QMix, cls), {'_qstr': 'mQ', 'maxsize': q._maxsize})
    return q


class Graph:
    default = None
    _delay = 1e-5
    task_name = None

    def __init__(self, name=None, graph=None):
        self.blocks = []
        self.name = auto_name(self, name=name)
        graph = graph or Graph.default
        if graph is not None:
            graph.add_block(self)
        self.log = reip.util.logging.getLogger(self, strrep='__repr__')

    # operators and internal

    def __enter__(self):
        Graph.default, self._previous = self, Graph.default
        return self

    def __exit__(self, *a):
        Graph.default, self._previous = self._previous, None

    def __reduce__(self):  # define pickling
        return pickle_worker(self)

    # str representations

    def __repr__(self):
        return '[{}{}]'.format(self.name, ''.join(
            ''.join('\n  '+x for x in str(b).splitlines())
            for b in self.blocks
        ))

    def status(self):
        return '[{}{}]'.format(self.name, ''.join(
            ''.join('\n  '+x for x in str(b.status()).splitlines())
            for b in self.blocks
        ))

    # transferring state across process boundaries

    def __import_state__(self, state):
        if state:
            blocks = state.pop('blocks', [])
            self.__dict__.update(state)
            for b, state in zip(self.blocks, blocks):
                b.__import_state__(state)

    def __export_state__(self):
        return export_state(self, blocks=[b.__export_state__() for b in self.blocks])

    # adding and getting blocks

    def add_block(self, block):
        self.blocks.append(block)
        block.task_name = self.task_name

    def get_block(self, name, require=True, match_graphs=False):
        found = next((
            b for b in self.iter_blocks(include_graphs=match_graphs) 
            if b.name == name), None)
        if require and found is None:
            raise KeyError(name)
        return found

    def all_blocks(self):
        return list(self.iter_blocks())

    def iter_blocks(self, include_graphs=False):
        for b in self.blocks:
            get_nested = getattr(b, 'iter_blocks', None)
            if get_nested is not None:
                if include_graphs:
                    yield b
                yield from get_nested()
            else:
                yield b

    # lifecycle

    @property
    def running(self):
        return all(b.running for b in self.blocks)

    def init(self):
        self.log.info('initializing')
        for block in self.blocks:
            block.init()

    def poll(self):
        if any(not b.running for b in self.blocks): # just added this to make graphs end immediately
            return False
        did_something = False  # let blocks finish
        for block in self.blocks:
            if not block.running:
                block.log.warning('not running')
                continue
            did_something = block.poll() or did_something
            time.sleep(self._delay)
        return did_something

    def finish(self):
        self.log.info('finishing')
        for block in self.blocks:
            block.finish()

    def run(self, *a, **kw):
        run(self, *a, **kw)


class Task(Graph):
    timeout = 10
    _process = None
    is_spawned = False

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.remote = remoteobj.Proxy(self)
        self.task_name = self.name

    def __reduce__(self):
        return pickle_worker(self)

    # str representations

    def __repr__(self):
        if self.is_spawned:
            return super().__repr__()
        return self.remote.super.attrs_('__repr__')(_default=super().__repr__)

    def status(self):
        if self.is_spawned:
            return super().status()
        return self.remote.super.status(_default=super().status)

    # process

    def _task_run(self):
        self.is_spawned = True
        try:
            with self._process.exc(raises=False):
                with self.remote.listen_(bg=False):
                    self.run()
        finally:
            self.is_spawned = False
            print(self.status())
            self.log.info(str(self.__export_state__()))
            return self.__export_state__()

    # state

    @property
    def running(self):
        if self.is_spawned:
            return super().running
        return self._process is not None and self._process.is_alive()

    @property
    def proc_up(self):
        return self._process is not None and self._process.is_alive()

    # lifecycle

    def init(self):
        if self.is_spawned:
            return super().init()

        if self._process is not None:
            if self._process.is_alive():
                return

        print('Spawning', self.name, flush=True)
        self._should_exit = mp.Event()
        self._process = remoteobj.util.process(self._task_run)
        self._process.start()  # make sure _process is assigned first

    _task_should_finish_up = False
    def poll(self):
        if self.is_spawned:
            self.remote.process_requests()
            doing_stuff = super().poll()
            if self._should_exit.is_set():
                self.log.info('task should exit !!')
            #if (not self._task_should_finish_up or not doing_stuff) and self._should_exit.is_set():
                raise BlockExit()
            return doing_stuff

        if self._process is None or not self._process.is_alive():
            raise BlockExit()
        return True

    def finish(self):
        if self.is_spawned:
            return super().finish()
        if self._process is None:
            return
        
        self.log.info('Joining')
        self._should_exit.set()
        self._process.join()#timeout=self.timeout)
        try:
            result = self._process.result or ()
            if result is None:
                raise ValueError('No value was returned from the task object. This is usually from a error raised in the task.')
            self.__import_state__(result)
        except Exception as e:
            self.log.exception(e)
            print('Could not pull block state from process. This means that block duration and processed counts will not be accurate.')
        self._process.exc.raise_any()
        self._process = None


def pickle_worker(obj, drop=()):  # tweaking how blocks get pickled
    cls = type(obj)
    drop = drop or ()
    attrs = obj.__dict__
    attrs = {k: v if k not in drop else None for k, v in attrs.items()}
    return unpickle_worker, (cls, attrs)

def unpickle_worker(cls, attrs):
    obj = object.__new__(cls)
    obj.__dict__ = attrs
    return obj


class CoreBlock:  # a basic base block to make sure that all required methods are defined
    def __init__(self, **kw):
        pass
        #if kw:
        #    print('got extra kw to', self.__class__.__name__, kw)
    def init(self): pass
    def process(self, *x, **kw): pass
    def finish(self): pass


class QWrap:  # wraps reip Customer so it works like the other queues
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.wrapped.maxsize = len(self.wrapped.store.items)
        self.wrapped._qstr = 'C'
    def __repr__(self):
        return _QMix.__repr__(self.wrapped)
    def __getattr__(self, k):
        return getattr(self.wrapped, k)
    def get(self, *a, **kw):
        x = self.wrapped.get(*a, **kw)
        self.wrapped.next()
        return x
    #    if x is not None:
    #        x, meta = x
    #        x = [x], meta
    #    return x
    def full(self):
        return len(self.wrapped) >= self.wrapped.maxsize


def process(block, *inputs):  # block process code (separate so we can use it in different places)
    if inputs and all(x is None for x in inputs):
        return
    inputs, meta = convert_inputs(*inputs)
    #self.log.debug('%d inputs. meta: %s', len(inputs), meta)
    result = block.process(*inputs, meta=meta)
    if result is None:
        return
    [result], meta = reip.block.prepare_output(result, meta)
    return result, meta




class Block:
    Cls = CoreBlock
    Graph = Graph
    Task = Task
    processed = dropped = 0
    task_name = None
    _delay = 1e-5
    duration = 0
    def __init__(self, *a, queue=10, block=None, max_processed=None, max_rate=None, wait_when_full=False, source_strategy=all, name=None, graph=None, _kw=None, log_level='info', **kw):
        self.max_queue = queue
        self.max_processed = max_processed
        self.wait_when_full = wait_when_full
        self.throttle = Throttler(max_rate)
        self.src_strategy = source_strategy

        if block is None:
            block = self.Cls(*a, **dict(kw, **(_kw or {})))
        self.block = block
        block.__block__ = block._ = self
        self.inputs = []
        #self.input_blocks = []
        self.output_customers = []

        # connect to parent graph
        self.name = auto_name(self, name=name)
        if graph is not False:
            graph = graph or Graph.default
            if graph is not None:
                graph.add_block(self)
        self.log = reip.util.logging.getLogger(self, log_level, strrep='__repr__')
        # wrap any unconventionally defined sources - like in B.audio.Mic
        srcs = getattr(block, 'sources', None)
        if srcs:
            for src in srcs:
                if src is not None:
                    self.inputs.append(QWrap(src))

    def __reduce__(self):
        return pickle_worker(self)

    # str representations

    def __repr__(self):
        return '[{:<12} [{}-{}] <{}> -{} i={} o={}]'.format(
            self.name, 
            len(self.inputs), len(self.output_customers),
            self.processed, self.dropped, self.inputs, self.output_customers)

    def status(self):
        dt = self.elapsed()
        return '[{} {} processed {} dropped. ran {:.3f}s. (avg: {:.5f} x/s)]'.format(
            self.name, self.processed, self.dropped, dt, self.processed/dt if dt else 0)

    # serializing across processes

    def __import_state__(self, state):
        if state:
            print(state)
            self.__dict__.update(state)

    def __export_state__(self):
        return export_state(self)

    # block connections

    def __call__(self, *inputs, throughput=None, strategy=None):
        #self.input_blocks.extend(inputs)
        self.inputs.extend(b.get_output(self) if isinstance(b, Block) else b for b in inputs)
        return self

    def to(self, block, **kw):
        return block(self, **kw)

    def get_output(self, other):
        if self.task_name == other.task_name:
            q = Queue(self.max_queue)
        else:
            q = mpQueue(self.max_queue)
        self.output_customers.append(q)
        return q

    def drain_inputs(self):
        results = [[] for _ in self.inputs]
        for q, out in zip(self.inputs, results):
            while not q.empty():
                out.append(q.get())
        return results

    # lifecycle

    def _reset(self):
        self.processed = 0
        self.dropped = 0
        self.duration = 0
        self.inner_time = 0

    def elapsed(self):
        return time.time() - self.inner_time if not self.duration else self.duration

    def init(self):
        self.log.info('initializing')
        self._reset()
        self.running = True
        self.outer_time = time.time()
        self.block.init()
        self.inner_time = time.time()

    def process(self, *inputs):
        return process(self.block, *inputs)
    
    def finish(self):  # TODO: wait for queue items?
        self.log.info('finishing')
        self.duration = time.time() - self.inner_time
        self.block.finish()
        self.outer_duration = time.time() - self.outer_time
        self.running = False

    def poll(self):
        #self.log.debug('poll')
        if not self.src_strategy(not q.empty() for q in self.inputs):
            #self.log.debug('no sources available %s', self.inputs)
            return False

        if self.throttle():
            #self.log.debug('throttling %d/%d', self.throttle.time_left, self.throttle.interval)
            return True

        if self.wait_when_full and any(q.full() for q in self.output_customers):
            #self.log.debug('output full: %s', self.output_customers)
            return True

        inputs = [qi.get(block=False) for qi in self.inputs]
        #self.log.debug('getting inputs: %s', inputs)
        result = self.process(*inputs)
        self.log.debug('got outputs: %s', type(result))
        if result is None:
            return True
        for q in self.output_customers:
            if q.full():
                q.get()
                self.dropped += 1
                if self.dropped == 1 or self.dropped % 10 == 0:
                    self.log.warning('%d samples dropped due to full queue', self.dropped)
            q.put(result)

        self.processed += 1
        if self.max_processed and self.processed >= self.max_processed:
            self.running = False
        return True

    def run(self, *a, **kw):
        run(self, *a, **kw)

    def __import_state__(self, state):
        if state:
            print(state)
            self.__dict__.update(state)

    def __export_state__(self):
        return export_state(self)


def wrap_blocks(cls, *blocks):
    return cls.Module(*blocks, cls=cls, Graph=cls.Graph, Task=cls.Task, Monitor=_monitor(cls))

Block.wrap_blocks = classmethod(wrap_blocks)



def export_state(self, *types, _getattrs=True, recurse=False, **kw):
    #if recurse:
    #    if isinstance(obj, (list, tuple, set)):
    #        return type(obj)(export_state(x, *types, _getattrs=False) for x in obj)
    #    if isinstance(obj, dict):
    #        return {k: export_state(obj[k], *types, _getattrs=False) for k in obj}
    if not _getattrs:
        return getattr(self, '__export_state__', lambda: self)()

    attrs = select_attrs(self, *(types + (int, float, str)), **kw)
    return {k: export_state(v, *types, _getattrs=False) for k, v in attrs.items()}


def select_attrs(obj, *types, drop=(), **kw):
    d = {k: v for k, v in obj.__dict__.items() if k not in drop and (not types or isinstance(v, types))}
    d.update(kw)
    return d

def convert_buffer(result):  # normalize the output of a queue
    if result is None:
        return None, {}
    #[x], meta = result
    #return x, meta
    return result


def convert_inputs(*inputs):  # take the items from multiple queues and convert them to inputs and meta
    xs = [convert_buffer(x) for x in inputs]
    inputs, meta = tuple(zip(*xs)) or ((), ())
    return inputs, Meta(inputs=meta)



class BaseBlocksModule(dict):  # wraps the blocks into a pseudo-module with block classes as attributes
    def __init__(self, *blocks, cls=Block, **kw):
        self.cls = cls
        super().__init__()
        self.update(*blocks, **kw)

    def _make_item(self, c, cls):
        return c

    def update(self, *blocks, cls=None, **kw):
        cls = self.cls if cls is None else cls
        super().update(((c.__name__, self._make_item(c, cls)) for c in blocks), **kw)
        return self

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(e)

    def __dir__(self):
        return list(self)


class BlocksModule(BaseBlocksModule):  # wraps a block in another block class (lets us use reip code with the waggle/ray wrappers)
    def _make_item(self, c, cls):
        return type(c.__name__, (cls,), {'Cls': c})


Block.Module = BlocksModule  # lets a block class override the Module class


class Throttler:  # use this to throttle a loop: th = Throttler(); for _ in loop: if th(): continue
    t_last = None
    def __init__(self, max_rate=None):
        self.interval = 1/max_rate if max_rate else None

    def clear(self):
        self.t_last = None
        return self

    def __call__(self):
        interval = self.interval
        if interval is None:
            return False
        last = self.t_last
        now = time.time()
        if last is None or (self.interval and now - last > interval):
            self.t_last = now
            print(last and now - last, interval)
            return False
        return True

    @property
    def elapsed(self):
        last = self.t_last
        return time.time() - last if last is not None else self.interval or 0

    @property
    def time_left(self):
        return max(0, self.interval - self.elapsed) if self.interval else 0


def _monitor(Block):
    class Monitor(Block):  # prints out graph status every x seconds
        def __init__(self, obj, key='status', max_rate=1/5., **kw):
            self.obj = obj
            self.str = getattr(obj, key or '__str__')
            super().__init__(max_rate=max_rate, n_inputs=0, n_outputs=0, name='monitor-{}'.format(getattr(obj, 'name', obj)), **kw)
            #self.block.process = self._process
    
        def process(self, *a, **kw):
            print(self.str())
    return Monitor


def example(Block):
    class BlockA(CoreBlock):
        def init(self):
            self.i = -1

        def process(self, meta):
            self.i += 1
            return [self.i], {}

        def finish(self):
            b = self.__block__
            b.log.info(b.drain_inputs())

    class BlockB(CoreBlock):
        def __init__(self, add):
            self.add = add

        def process(self, x, meta):
            self._.log.info(x)
            return [x + self.add], {}

        def finish(self):
            b = self.__block__
            b.log.info(b.drain_inputs())

    class Print(CoreBlock):
        def process(self, x, meta):
            self._.log.info(x)
            return [x], {}

        def finish(self):
            b = self.__block__
            b.log.info(b.drain_inputs())

    B = Block.wrap_blocks(BlockA, BlockB, Print)
    return B

B = example(Block)


def test(slow=False, duration=10, n=20):
    kw = dict(max_processed=n)
    if slow:
        kw['max_rate'] = 5
    print(kw)

    with B.Graph() as g:
        x1 = B.BlockA(**kw).to(B.BlockB(10)).to(B.BlockB(10)).to(B.Print())
        with B.Graph():
            B.BlockA(**kw).to(B.Print())
        with B.Task():
            x1.to(B.BlockB(50)).to(B.Print())
        B.Monitor(g, None)

    assert g.get_block('print') is x1

    print(g)
    print(g.run(duration=duration))
    print(g.status())


if __name__ == '__main__':
    import fire
    fire.Fire(test)

