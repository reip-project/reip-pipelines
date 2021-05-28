import queue
import time
import reip

import ray
ray.init()

import base_app
from base_app import Block as BaseBlock, Graph, convert_inputs

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


class Block(base_app.Block):
    Graph = Graph
    Task = Task
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


if __name__ == '__main__':
    B = base_app.example(Block)

    with B.Graph() as g:
        x1 = B.BlockA(max_processed=10).to(B.BlockB(10)).to(B.BlockB(10)).to(B.Print())
        with B.Graph():
            B.BlockA(max_processed=10).to(B.Print())
        with B.Task():
            x1.to(B.BlockB(50)).to(B.Print())

    print(g)
    print(g.run())
