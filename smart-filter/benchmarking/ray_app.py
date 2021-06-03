import queue
import time
import functools

import reip

import ray

import base_app
from base_app import Block as BaseBlock, Graph, convert_inputs


def ray_init(*a, **kw):
    # if ray_init.done:
    #     print('ray already initialized.')
    #     return
    if not ray.is_initialized():
        ray.init(*a, ignore_reinit_error=True, num_cpus=4, **kw)
#     ray_init.done = True
# ray_init.done = False


import reip
class QMix(base_app.QMix):
    cache = None
    def spawn(self):
        self.cache = None

    def qsize(self):
        return super().qsize() + int(self.cache is not None)
    
    def empty(self):
        return self.get(peek=True) is None  # make empty take into consideration if the future is ready or not
    
    def get(self, block=False, timeout=None, peek=False):
        fut = self.cache
        if fut is None:  # get the next element
            fut = super().get(block=block, timeout=timeout)
            if fut is None:  # there's nothing right now
                return
            self.cache = fut
        if not ray.wait([fut], timeout=0, fetch_local=False)[0]:  # not ready
            return
        # the future is ready, but don't pull the item, let the future just be passed to the next function
        if not peek:
            self.cache = None
        return fut

    def _drain(self):
        if self.cache is not None:
            yield self.cache
        while self.qsize():
            fut = self.get()
            if fut is not None:
                yield fut
    
    def join(self):
        # ray.cancel(list(self._drain()))
        ray.wait(list(self._drain()))

#Queue, mpQueue = base_app.extend_queue(QMix)

import collections
import queue
class Queue2(collections.deque):
    def __init__(self, maxsize, strategy='all'):
        self.maxsize = maxsize
        self.dropped = 0
        self.strategy = strategy
        super().__init__(maxlen=maxsize)

    def __repr__(self):
        return 'dQ({}/{} -{})'.format(len(self), self.maxsize, self.dropped)

    def empty(self):
        return self.get(peek=True) is None  # make empty take into consideration if the future is ready or not

    def full(self):
        return len(self) >= self.maxsize

    def put(self, x, block=False, timeout=None):
        if self.full():
            raise queue.Full()
            #self.dropped += 1
            #print('dropped when putting to', self)
            #return False
        self.appendleft(x)

    def _check_ready(self, x):
#        return ray.get(x, timeout=0) is not None
        return ray.wait([x], timeout=0, fetch_local=False)[0]

    def get(self, block=False, timeout=None, peek=False):
        if not self:
            return
        if self.strategy == 'latest':
            it = iter(list(self))
            try:
                for x in it:
                    if self._check_ready(x):
                        # if not peek:
                        #     self.clear()
                        self.pop()
                        return x#.get()
            finally:
                if not peek:
                    for x in it:  # remove any remaining values
                        #print('dropping non-latest sample', self)
                        self.pop()
                        #self.dropped += 1
            return
        if not self._check_ready(self[-1]):
            return
        if peek:
            return self[-1]
        return self.pop()#.get()

    def join(self):
        oids = list(self)
        # print('awaiting', oids, self)
        if oids:
            # ray.cancel(oids)
            ray.wait(oids)
            # print(ray.get(oids))



@ray.remote(num_cpus=1)
class BlockAgent:
    inner_time = None
    duration = None
    # processed = 0
    def __init__(self, block):
        self.block = block
        print('initializing ray actor for', str(block))

    def init(self):
        self.processed = 0
        time.sleep(1)
        self.block.log.info(reip.util.text.blue('initializing'))
        self.outer_time = time.time()
        self.block.init()
        self.inner_time = time.time()
        self.block.log.info(reip.util.text.green('ready'))

    def process(self, *inputs):
        # print(inputs)
        output = base_app.process(self.block, *inputs)
        # print(output)
        # self.processed += 1
        return output

    def finish(self):
        self.block.log.info(reip.util.text.blue('finishing'))
        self.duration = time.time() - self.inner_time
        self.block.finish()
        self.outer_duration = time.time() - self.outer_time
        self.block.log.info(reip.util.text.green('done'))

    def get(self, k):
        return getattr(self, k)

    def set(self, k, v):
        return setattr(self, k, v)


def maybeget(futs, get=True):
    return ray.get(futs) if get else futs

class Graph(base_app.Graph):
    # _delay = 1e-2
    def init(self, get=True):
        self.log.info(reip.util.text.blue('initializing'))
        return maybeget([fut for block in self.blocks for fut in base_app.aslist(block.init(get=False))], get)

    def finish(self, get=True):
        self.log.info(reip.util.text.blue('finishing'))
        return maybeget([fut for block in self.blocks for fut in base_app.aslist(block.finish(get=False))], get)


class Task(Graph):  # XXX: ray does not need to spawn a process because blocks are their own process
    pass

Queue, mpQueue = base_app.extend_queue(QMix)


def agent_property(name):
    def getter(self):
        return ray.get(self.agent.get.remote(name))
    def setter(self, value):
        ray.get(self.agent.set.remote(name, value))
    getter.__name__ = setter.__name__ = name
    prop = property(getter, setter)
    return prop


class Block(base_app.Block):
    Graph = Graph
    Task = Task
    Queue = Queue2
    # Queue = Queue
    # Queue = mpQueue = staticmethod(mpQueue)
    wait_when_full = True

    def __init__(self, *a, queue=100, **kw):
        super().__init__(*a, queue=queue, **kw)
        self.agent = BlockAgent.remote(self.block)

    duration = agent_property('duration')
    inner_time = agent_property('inner_time')
    # processed = agent_property('processed')

    def init(self, get=True):
        self.processed = 0
        self.dropped = 0
        self.running = True
        return maybeget(self.agent.init.remote(), get)

    def sources_available(self):
        futs = (q.get(peek=True) for q in self.inputs)
        futs = (ray.get(f, timeout=0) if f is not None else None for f in futs)
        return self.src_strategy(x is not None for x in futs)

    def process(self, *inputs):
        fut = self.agent.process.remote(*inputs)
        return fut

    def finish(self, get=True):
        for q in self.output_customers:
            q.join()
        self.running = False
        return maybeget(self.agent.finish.remote(), get)


B = base_app.example(Block)
test = functools.partial(base_app.test, B=B)

if __name__ == '__main__':
    ray_init()
    import fire
    fire.Fire(test)
