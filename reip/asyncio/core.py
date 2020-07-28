'''




'''
import asyncio
import ray

from .ring_buffer import RingBuffer
from . import util
from reip.simple.util import Timer


__all__ = ['init', 'Block', 'Graph', 'run_blocks']


def init(*a, **kw):
    ray.init(*a, **kw)


######################
# Block Definition
######################


BLANK = object()
TERMINATE = object()


class Block():
    '''This is the base instance of a block.'''
    exec_mode = 'thread'

    def __init__(self, queue=100, n_source=1, n_sink=1, exec_mode=None, graph=None):
        self.sources = [None for _ in range(n_source)]
        self.sinks = [RingBuffer(queue) for _ in range(n_sink)]
        self.exec_mode = exec_mode or self.exec_mode
        (graph or Graph.default).add(self)

    def __repr__(self):
        return '[Block({}): {} ({} in, {} out)]'.format(
            id(self), self.__class__.__name__,
            len(self.sources), len(self.sinks))

    # User Interface

    def init(self):
        '''Initialize the block.'''

    def process(self, *xs, meta=None):
        '''Process data.'''
        return xs, meta

    def finish(self):
        '''Cleanup.'''

    # Graph definition

    def __call__(self, *others, **kw):
        for i, other in enumerate(others):
            self.sources[i] = other.sinks[0].gen_source(**kw)
        return self

    def to(self, *others, squeeze=True, **kw):
        outs = [other(self, **kw) for other in others]
        return outs[0] if squeeze and len(outs) == 1 else outs

    # Block mechanics

    async def wait_for_sources(self, **kw):
        '''Wait for sources to be ready.'''
        return await asyncio.gather(*[s.wait(**kw) for s in self.sources])

    async def gather_sources(self, **kw):
        return await asyncio.gather(*[s.get(**kw) for s in self.sources])

    def push_sinks(self, outs, meta):
        '''send the data to the sink'''
        for s, out in zip(self.sinks, outs):
            if s is not None:
                s.put_nowait((out, meta))

    def next_sources(self):
        '''increment the block sources'''
        for s in self.sources:
            s.next()


######################
# Block remote interface
######################


class BlockRunner:
    '''This wraps the block using a Ray Actor which pickles it and brings it
    to its own process. This lets us run the block asynchronously without
    having to use asynchronous processing code for blocks.
    '''
    def __init__(self, obj):
        self.obj = obj
        self.timer = Timer(str(self.obj))

    def __str__(self):
        return '[BlockActor({})]'.format(self.obj)

    def init(self):
        with self.timer('init', 'Initialization'):
            self.obj.init()

    def process(self, inputs):
        with self.timer('process', 'Processing', output=True):
            xs, meta = prepare_input(inputs)
            outputs = self.obj.process(*xs, meta=meta)
            return prepare_output(outputs, input_meta=meta)

    def finish(self):
        try:
            with self.timer('finish', 'Finishing'):
                return self.obj.finish()
        finally:
            print(self.obj, self.timer)


def prepare_input(inputs):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, meta = zip(*inputs) if inputs else ((), ())
    return (
        # XXX: ... is a sentinel for empty outputs - how should we handle them here??
        #      if there's a blank in the middle
        [] if all(b is ... for b in bufs) else bufs,
        util.Stack({}, *meta))


def prepare_output(outputs, input_meta=None): # XXX: unfinished
    '''Take the inputs from block.process and prepare to be passed to block.sinks.'''
    if any(outputs is X for X in (None, TERMINATE)):
        return outputs

    bufs, meta = None, None
    if isinstance(outputs, tuple):
        if len(outputs) == 2:
            bufs, meta = outputs

    if input_meta:
        meta = util.Stack(meta, input_meta)
    return bufs or (...,), meta or util.Stack()


RemoteRunner = ray.remote(BlockRunner)
LocalRunner = util.ray_local(BlockRunner)


def as_ray_worker(obj):
    if obj.exec_mode == 'process':
        return RemoteRunner.remote(obj)
    return LocalRunner(obj)


######################
# Graph management
######################


class Graph:
    default = None  # the default graph instance
    _previous = None  # the previous default graph instance
    def __init__(self):
        self.blocks = []

    def __str__(self):
        return '<Graph {}\n>'.format(
            ''.join('\n\t{}'.format(b) for b in self.blocks))

    # global instance management

    @classmethod
    def get_default(cls):
        return cls.default

    def __enter__(self):
        return self.as_default()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_previous()

    def as_default(self):
        self._previous, Graph.default = Graph.default, self
        return self

    def restore_previous(self):
        if self._previous is not None:
            Graph.default, self._previous = self._previous, None
        return self

    # block management

    def add(self, block):
        '''Add block to graph.'''
        if isinstance(block, Block):
            self.blocks.append(block)

    def run(self, *extra_blocks, **kw):
        '''Run all blocks in graph.'''
        return run_blocks(*self.blocks, *extra_blocks, **kw)

# create an initial default graph
Graph.default = Graph()


######################
# Block Execution
######################

'''

Queue objects need to be brought back to the main process

Sources and sinks should be separate from the actual processing blocks.

Concepts:
 - Blocks & Custom Blocks
    - a basic
    - user implemented code with a simple interface
 - RemoteRunner
    - a wrapper around a block object which will pickle it and run it remotely
 -

Currently we have two instances of the block. We have the original local instance
and the remote pickled instance. We use the remote instance for processing and the
local instance for queue-ing.

'''


async def _run_block(block, block_run, shutting_down):
    try:
        # initialize the remote instance
        await block_run.init.remote()
        print('initializing', block)

        while not shutting_down.is_set():
            # wait for all sources to have elements
            await block.wait_for_sources()
            # get input data
            inputs = await block.gather_sources()
            # run block code
            outputs = await block_run.process.remote(inputs)
            # watch output for terminate flag
            if outputs is TERMINATE:
                break
            # increment the sources
            block.next_sources()
            # send outputs
            if outputs is not None:
                out, meta = outputs
                block.push_sinks(out, meta)

    except KeyboardInterrupt:
        print('interrupting block', block)
    finally:
        block_run.finish.remote()


def run_blocks(*blocks, **kw):
    '''Run each block in an asyncio event loop.'''
    # Wrap the block in a Ray Actor. This pickles the block and launches it
    # as its own process.
    block_pairs = [(b, as_ray_worker(b)) for b in blocks]
    # add blocks to the event loop
    loop = asyncio.get_event_loop()
    # use a common flag to shut down all events
    shutting_down = asyncio.Event(loop=loop)
    # initialize all of the tasks
    tasks = asyncio.gather(*[
        _run_block(b, b_act, shutting_down)
        for b, b_act in block_pairs])
    # run tasks in loop
    try:
        loop.run_until_complete(tasks)
    except KeyboardInterrupt as e:
        print("Loop interrupted. Canceling tasks...")
        for b in blocks:
            print('\t', b)
        shutting_down.set()
        # tasks.cancel()
        loop.run_until_complete(tasks)
        # tasks.exception()
    # finally:
    #     loop.stop()
    #     loop.close()

    # finally:
    #     loop.close()
