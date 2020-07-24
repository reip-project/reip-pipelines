'''




'''

import time
import asyncio
import ray

from .ring_buffer import RingBuffer
from . import util
from reip.simple.util import Timer


def init(*a, **kw):
    ray.init(*a, **kw)


######################
# Block Definition
######################


BLANK = object()


class Block():
    '''This is the base instance of a block.'''
    terminate = False

    def __init__(self, queue=100, n_source=1, n_sink=1):
        self.sources = [None for _ in range(n_source)]
        self.sinks = [RingBuffer(queue) for _ in range(n_sink)]

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

    # Block mechanics

    def __call__(self, other, **kw):
        self.sources[0] = other.sinks[0].gen_source(**kw)
        return self

    def to(self, other, **kw):
        other.sources[0] = self.sinks[0].gen_source(**kw)
        return other

    async def wait_for_sources(self):
        return await asyncio.gather(*[s.wait() for s in self.sources])

    async def gather_sources(self):
        inputs = await asyncio.gather(*[s.get() for s in self.sources])
        return prepare_input(inputs)

    def push_sinks(self, outputs, **kw):
        outs, meta = prepare_output(outputs, **kw)
        for s, out in zip(self.sinks, outs):
            s.put_nowait((out, meta))

    def next_sources(self):
        for s in self.sources:
            s.next()

    def push_next(self, outputs, **kw):
        # increment the block sources
        self.next_sources()
        # send the data to the sink
        self.push_sinks(outputs, **kw)


def prepare_input(inputs):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, meta = zip(*inputs) if inputs else ((), ())
    return (
        # XXX: BLANK is a sentinel for empty outputs - how should we handle them here??
        #      if there's a blank in the middle
        [] if all(b is BLANK for b in bufs) else bufs,
        util.Stack({}, *meta))

def prepare_output(outputs, input_meta=None): # XXX: unfinished
    '''Take the inputs from block.process and prepare to be passed to block.sinks.'''
    bufs, meta = None, None
    if isinstance(outputs, tuple):
        if len(outputs) == 2:
            bufs, meta = outputs

    if input_meta:
        meta = util.Stack(meta, input_meta)
    return bufs or (BLANK,), meta


@ray.remote
class RemoteRunner:
    '''This wraps the block using a Ray Actor which pickles it and brings it
    to its own process. This lets us run the block asynchronously without
    having to use asynchronous processing code for blocks.
    '''
    def __init__(self, obj):
        self.obj = obj
        self.timer = Timer(str(self.obj))

    def init(self):
        with self.timer('init', 'Initialization'):
            self.obj.init()

    def process(self, *xs, meta=None):
        with self.timer('process', 'Processing', output=True):
            return self.obj.process(*xs, meta=meta)

    def finish(self):
        try:
            with self.timer('finish'):
                return self.obj.finish()
        finally:
            print(self.obj, self.timer)

    def terminated(self):
        return self.obj.terminate


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


async def run_block(block, block_run, shutting_down):
    try:
        # initialize the remote instance
        await block_run.init.remote()
        print('initializing', block)

        while not shutting_down.is_set():
            # wait for all sources to have elements
            await block.wait_for_sources()
            # get input data
            bufs, meta = await block.gather_sources()
            # run block code
            outputs = await block_run.process.remote(*bufs, meta=meta)
            # send outputs
            if outputs is not None:
                block.push_next(outputs, input_meta=meta)

    except KeyboardInterrupt:
        print('interrupting block', block)
    finally:
        block_run.finish.remote()  # XXX: this never gets called



def run(*blocks, **kw):
    '''Run each block in an asyncio event loop.'''
    # Wrap the block in a Ray Actor. This pickles the block and launches it
    # as its own process.
    block_pairs = [(b, RemoteRunner.remote(b)) for b in blocks]
    # add blocks to the event loop
    loop = asyncio.get_event_loop()
    # use a common flag to shut down all events
    shutting_down = asyncio.Event(loop=loop)
    # create all of the tasks
    tasks = asyncio.gather(*[
        run_block(b, b_act, shutting_down)
        for b, b_act in block_pairs])
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
