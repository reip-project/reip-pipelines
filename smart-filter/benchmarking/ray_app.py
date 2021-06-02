import queue
import time
import functools

import reip

import ray

import base_app
from base_app import Block as BaseBlock, Graph, convert_inputs


def ray_init(*a, **kw):
    if ray_init.done:
        print('ray already initialized.')
        return
    ray.init(*a, ignore_reinit_error=True, **kw)
    ray_init.done = True
ray_init.done = False


class QMix(base_app.QMix):
    cache = None
    def spawn(self):
        self.cache = None

    def empty(self):
        return self.get(peek=True) is not None  # make empty take into consideration if the future is ready or not

    def get(self, block=False, timeout=None, peek=False):
        fut = self.cache
        if fut is None:  # get the next element
            self.cache = fut = super().get(block=block, timeout=timeout)
        if fut is None:  # there's nothing right now
            return
        if not ray.wait([fut], timeout=0, fetch_local=False)[0]:  # not ready
            return
        # the future is ready, but don't pull the item, let the future just be passed to the next function
        if not peek:
            self.cache = None
        return fut

    def join(self):
        if self.cache is not None:
            ray.cancel(self.cache)
            self.cache = None
        while self.qsize():
            fut = self.get()
            if fut is not None:
                ray.cancel(fut)

#Queue, mpQueue = base_app.extend_queue(QMix)



@ray.remote
class BlockAgent:
    duration = None
    def __init__(self, block):
        self.block = block
        print('initializing ray init', block)

    def init(self):
        self.log.info(reip.util.text.blue('initializing'))
        self.outer_time = time.time()
        self.block.init()
        self.inner_time = time.time()
        self.log.info(reip.util.text.green('ready'))

    def process(self, *inputs):
        # print(1, self.block.__block__.name)
        if inputs and all(x is None for x in inputs):
            return
        # print(2, self.block.__block__.name)
        inputs, meta = convert_inputs(*inputs)
        print(meta)
        return self.block.process(*inputs, meta=meta)

    def finish(self):
        self.log.info(reip.util.text.blue('finishing'))
        self.duration = time.time() - self.inner_time
        self.block.finish()
        self.outer_duration = time.time() - self.outer_time
        self.log.info(reip.util.text.green('done'))

    def get_duration(self):
        return self.duration


def maybeget(futs, get=True):
    return ray.get(futs) if get else futs

class Graph(base_app.Graph):
    def init(self, get=True):
        print(self.name, 'initializing', flush=True)
        futs = [fut for block in self.blocks for fut in base_app.aslist(block.init(get=False))]
        return maybeget(futs, get)

    def finish(self, get=True):
        print(self.name, 'finishing', flush=True)
        futs = [fut for block in self.blocks for fut in base_app.aslist(block.finish(get=False))]
        return maybeget(futs, get)

    def run(self, *a, **kw):
        ray_init()
        return super().run(*a, **kw)

    #def run(self, duration=None):
    #    try:
    #        t0 = time.time()
    #        self.init()
    #        while self.running:
    #            if duration and time.time() - t0 >= duration:
    #                break
    #            self.poll()
    #            time.sleep(self.delay)
    #    except base_app.BlockExit:
    #        print('Exiting...')
    #    except KeyboardInterrupt:
    #        print('Interrupting...')
    #    finally:
    #        self.finish()

class Task(Graph):  # XXX: ray does not need to spawn a process because blocks are their own process
    pass

Queue, mpQueue = base_app.extend_queue(QMix)

class Block(base_app.Block):
    Graph = Graph
    Task = Task
    #Queue = Queue
    Queue = mpQueue = staticmethod(mpQueue)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.agent = BlockAgent.remote(self.block)

    @property
    def duration(self):
        return ray.get(self.agent.get_duration.remote())

    def init(self, get=True):
        self.processed = 0
        self.dropped = 0
        self.running = True
        return maybeget(self.agent.init.remote(), get)

    def process(self, *inputs):
        return self.agent.process.remote(*inputs)

    def finish(self, get=True):
        return maybeget(self.agent.finish.remote(), get)


B = base_app.example(Block)
test = functools.partial(base_app.test, B=B)

if __name__ == '__main__':
    ray_init()
    import fire
    fire.Fire(test)
