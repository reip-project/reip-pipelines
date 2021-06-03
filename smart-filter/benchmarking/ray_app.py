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
        ray.init(*a, ignore_reinit_error=True, num_cpus=-2, **kw)
#     ray_init.done = True
# ray_init.done = False


import reip

import queue
import collections
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
        self.appendleft(x)

    def _check_ready(self, x):
        return ray.wait([x], timeout=0, fetch_local=False)[0]

    def get(self, block=False, timeout=None, peek=False):
        if not self:
            return

        if self.strategy == 'latest':
            it = iter(list(self))
            for i, x in enumerate(it):
                if x is None:
                    continue
                # check if the buffer is ready
                if not self._check_ready(x):
                    continue
                # check if the buffer is None
                if ray.get(x, timeout=0) is None:
                    print('dropping None sample latest')
                    self[i] = None
                    continue
                # the buffer is not None
                if not peek:
                    self.pop()  # remove that value
                    for x in it:  # remove skipped values
                        self.pop()
                return x
            return
        
        # if self.gotcha:
        #     print(1, peek, self, list(self))
        # iterate from oldest to newest
        i = len(self)
        while i > 0:
            i -= 1
            x = self[i]
            if x is None:
                if not peek:
                    self.pop()
                continue

            if not self._check_ready(x):
                return
            if not peek:
                self.pop()
            if ray.get(x, timeout=0) is None:
                # print('dropping None sample', id(self))
                # self.gotcha = True
                continue
            # if self.gotcha:
            #     print(2, peek, x, list(self))
            return x
    # gotcha = False


    def join(self):
        oids = [x for x in self if x is not None]
        # print('awaiting', oids, self)
        if oids:
            # ray.cancel(oids)
            ray.wait(oids)
            # print(ray.get(oids))



@ray.remote
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
    _delay = 1e-2
    def init(self, get=True):
        self.log.info(reip.util.text.blue('initializing'))
        return maybeget([fut for block in self.blocks for fut in base_app.aslist(block.init(get=False))], get)

    def finish(self, get=True):
        self.log.info(reip.util.text.blue('finishing'))
        return maybeget([fut for block in self.blocks for fut in base_app.aslist(block.finish(get=False))], get)


class Task(Graph):  # XXX: ray does not need to spawn a process because blocks are their own process
    pass


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
    # wait_when_full = True

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
