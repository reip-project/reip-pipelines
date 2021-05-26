import queue
import time
import remoteobj
import multiprocessing as mp
import reip


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
                break
            worker.poll()
            time.sleep(worker.delay)
    except BlockExit:
        print('Exiting...')
    except KeyboardInterrupt:
        print('Interrupting...')
    finally:
        worker.finish()


class Graph:
    default = None
    delay = 1e-5
    task_name = None
    def __init__(self, name=None):
        self.blocks = []
        self.name = auto_name(self, name=name)
        graph = Graph.default
        if graph is not None:
            graph.blocks.append(self)
            self.task_name = graph.task_name

    def __enter__(self):
        Graph.default, self._previous = self, Graph.default
        return self

    def __exit__(self, *a):
        Graph.default, self._previous = self._previous, None

    def __repr__(self):
        return '[{}{}]'.format(self.name, ''.join(
            ''.join('\n  '+x for x in str(b).splitlines())
            for b in self.blocks
        ))

    @property
    def running(self):
        return all(b.running for b in self.blocks)

    def init(self):
        for block in self.blocks:
            block.init()

    def poll(self):
        did_something = False  # let blocks finish
        for block in self.blocks:
            if not block.running:
                continue
            did_something = block.poll() or did_something
        return did_something

    def finish(self):
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

    def _task_run(self):
        self.is_spawned = True
        try:
            return self.run()
        finally:
            pass

    @property
    def running(self):
        if self.is_spawned:
            return super().running
        return self._process is not None and self._process.is_alive()

    def init(self):
        if self.is_spawned:
            return super().init()

        if self._process is not None:
            if self._process.is_alive():
                return

        print('Spawning', self.name, flush=True)
        self._should_exit = mp.Event()
        self._process = remoteobj.util.process(self._task_run).start()

    def poll(self):
        if self.is_spawned:
            doing_stuff = super().poll()
            if not doing_stuff and self._should_exit.is_set():
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

        print('Joining', self.name, flush=True)
        self._should_exit.set()
        self._process and self._process.join(timeout=self.timeout)
        self._process = None



class CoreBlock:
    def init(self): pass
    def process(self, *x, **kw): pass
    def finish(self): pass

class Block:
    Cls = CoreBlock
    Graph = Graph
    Task = Task
    processed = dropped = 0
    def __init__(self, *a, queue=10, block=None, max_processed=None, max_rate=None, wait_when_full=False, name=None, **kw):
        self.max_queue = queue
        self.max_processed = max_processed
        self.wait_when_full = wait_when_full
        self.throttle = Throttler(max_rate)

        if block is None:
            block = self.Cls(*a, **kw)
        self.block = block
        block.__block__ = self
        self.inputs = []
        self.input_blocks = []
        self.output_customers = []

        self.name = auto_name(self, name=name)
        graph = Graph.default
        if graph is not None:
            graph.blocks.append(self)
            self.task_name = graph.task_name
        self.log = reip.util.logging.getLogger(self, strrep='__repr__')

    def __repr__(self):
        return '[{:<12} [{}-{}] <{}> -{}]'.format(
            self.name, 
            len(self.inputs), len(self.output_customers),
            self.processed, self.dropped)

    def __call__(self, *inputs):
        self.input_blocks.extend(inputs)
        self.inputs.extend(b.get_output(self) if isinstance(b, Block) else b for b in inputs)
        return self

    def to(self, block):
        return block(self)

    def get_output(self, other):
        if self.task_name == other.task_name:
            q = queue.Queue(self.max_queue)
        else:
            q = mp.Queue(self.max_queue)
        self.output_customers.append(q)
        return q

    def drain_inputs(self):
        results = [[] for _ in self.inputs]
        for q, out in zip(self.inputs, results):
            while not q.empty():
                out.append(q.get())
        return results

    def _reset(self):
        self.processed = 0
        self.dropped = 0

    def init(self):
        print(self.name, 'initializing', flush=True)
        self._reset()
        self.running = True
        self.outer_time = time.time()
        self.block.init()
        self.inner_time = time.time()

    def process(self, *inputs):
        return self.block.process(*inputs)
    
    def finish(self):  # TODO: wait for queue items?
        print(self.name, 'finishing', flush=True)
        self.duration = time.time() - self.inner_time
        self.block.finish()
        self.outer_duration = time.time() - self.outer_time

    def poll(self):
        if not all(not q.empty() for q in self.inputs):
            return False

        if self.throttle():
            return True

        if self.wait_when_full and any(q.full() for q in self.output_customers):
            return True

        inputs = [qi.get() for qi in self.inputs]
        result = self.block.process(*inputs)
        for q in self.output_customers:
            if q.full():
                q.get()
                self.dropped += 1
                print('sample dropped due to full queue in', self.block, flush=True)
            q.put(result)

        self.processed += 1
        if self.max_processed and self.processed > self.max_processed:
            self.running = False
        return True

    def run(self, *a, **kw):
        run(self, *a, **kw)

    def status(self):
        dt = self.duration
        return '[{} {} processed {} dropped. ran {:.3f}s. (avg: {:.5f} x/s)]'.format(
            self.block.__class__.__name__, self.processed, self.dropped, dt, self.processed/dt)

    @classmethod
    def wrap_blocks(cls, *blocks):
        return BlocksModule(*blocks, cls=cls, Graph=cls.Graph, Task=cls.Task)


class BlocksModule(dict):
    def __init__(self, *blocks, cls=Block, **kw):
        self.cls = cls
        super().__init__()
        self.update(*blocks, **kw)

    def update(self, *blocks, cls=None, **kw):
        cls = self.cls if cls is None else cls
        super().update(((c.__name__, type(c.__name__, (cls,), {'Cls': c})) for c in blocks), **kw)
        return self

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(e)

    def __dir__(self):
        return list(self)


class Throttler:
    t_last = None
    def __init__(self, max_rate=None):
        self.interval = 1/max_rate if max_rate else None

    def clear(self):
        self.t_last = None
        return self

    def __call__(self):
        last = self.t_last
        now = time.time()
        if last is None or (self.interval and now - last > self.interval):
            self.t_last = now
            return True
        return False



def example(Block):
    class BlockA(CoreBlock):
        def init(self):
            self.i = -1

        def process(self):
            self.i += 1
            return self.i

        def finish(self):
            b = self.__block__
            print(b.name, b.drain_inputs(), flush=True)

    class BlockB(CoreBlock):
        def __init__(self, add):
            self.add = add

        def process(self, x):
            return x + self.add

        def finish(self):
            b = self.__block__
            print(b.name, b.drain_inputs(), flush=True)

    class Print(CoreBlock):
        def process(self, x):
            print(x, flush=True)
            return x

        def finish(self):
            b = self.__block__
            print(b.name, b.drain_inputs(), flush=True)

    B = Block.wrap_blocks(BlockA, BlockB, Print)
    return B

if __name__ == '__main__':
    B = example(Block)

    with B.Graph() as g:
        x1 = B.BlockA(max_processed=10).to(B.BlockB(10)).to(B.BlockB(10)).to(B.Print())
        with B.Graph():
            B.BlockA(max_processed=10).to(B.Print())
        with B.Task():
            x1.to(B.BlockB(50)).to(B.Print())

    print(g)
    print(g.run())