import queue
import time
import reip

import ray
ray.init()

import base_app
from base_app import Block as BaseBlock, Graph, convert_inputs



class QMix(base_app.QMix):
    cache = None
    def spawn(self):
        self.cache = None

    def get(self, block=False, timeout=None):
        fut = self.cache
        if fut is None:  # get the next element
            self.cache = fut = super().get(block=block, timeout=timeout)
        if fut is None:  # there's nothing right now
            return
        if not ray.wait([fut], timeout=0, fetch_local=False)[0]:  # not ready
            return
        return fut  # the future is ready, but don't pull the item

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

    def init(self):
        self.outer_time = time.time()
        self.block.init()
        self.inner_time = time.time()

    def process(self, *inputs):
        # print(1, self.block.__block__.name)
        if inputs and all(x is None for x in inputs):
            return
        # print(2, self.block.__block__.name)
        inputs, meta = convert_inputs(*inputs)
        print(meta)
        return self.block.process(*inputs, meta=meta)

    def finish(self):
        self.duration = time.time() - self.inner_time
        self.block.finish()
        self.outer_duration = time.time() - self.outer_time

    def get_duration(self):
        return self.duration



class Graph(base_app.Graph):
    def init(self):
        print(self.name, 'initializing', flush=True)
        return [fut for block in self.blocks for fut in base_app.aslist(block.init())]

    def finish(self):
        print(self.name, 'finishing', flush=True)
        return [fut for block in self.blocks for fut in base_app.aslist(block.finish())]

    def run(self, duration=None):
        try:
            t0 = time.time()
            ray.get(self.init())
            while self.running:
                if duration and time.time() - t0 >= duration:
                    break
                self.poll()
                time.sleep(self.delay)
        except base_app.BlockExit:
            print('Exiting...')
        except KeyboardInterrupt:
            print('Interrupting...')
        finally:
            ray.get(self.finish())

class Task(Graph):  # XXX: ray does not need to spawn a process because blocks are their own process
    pass

Queue, mpQueue = base_app.extend_queue(QMix)

class Block(base_app.Block):
    Graph = Graph
    Task = Task
    Queue = Queue
    mpQueue = staticmethod(mpQueue)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.agent = BlockAgent.remote(self.block)

    @property
    def duration(self):
        return ray.get(self.agent.get_duration.remote())

    def init(self):
        self.processed = 0
        self.dropped = 0
        self.running = True
        return self.agent.init.remote()

    def process(self, *inputs):
        return self.agent.process.remote(*inputs)

    def finish(self):  # TODO: wait for queue items?
        return self.agent.finish.remote()






# with Graph() as g:
#     cam1 = Block(core.Camera(), max_processed=100)
#     cam2 = Block(core.Camera())

#     stitch = Block(core.Stitch(), cam1, cam2)
#     filtered = Block(core.MotionFilter(), stitch)
#     ml = Block(core.ML(), filtered)

#     write_video = Block(core.Write(), filtered)
#     write_ml = Block(core.Write(), ml)


# try:
#     g.run()
# except KeyboardInterrupt:
#     print('\nInterrupted.\n')
# finally:
#     for b in g.blocks:
#         print(b.status())


B = base_app.example(Block)
test = functools.partial(base_app.test, B=B)

if __name__ == '__main__':
    import fire
    fire.Fire(test)
