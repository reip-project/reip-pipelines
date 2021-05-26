import reip
import base_app

class Graph(reip.Graph):
    def __init__(self, *a, name=None, **kw):
        super().__init__(*a, name=base_app.auto_name(block, name=name), **kw)

class Task(reip.Task):
    def __init__(self, *a, name=None, **kw):
        super().__init__(*a, name=base_app.auto_name(block, name=name), **kw)

class Block(reip.Block):
    Cls = base_app.CoreBlock
    Graph = Graph
    Task = Task
    wrap_blocks = base_app.Block.wrap_blocks

    def __init__(self, block, **kw):
        if block is None:
            block = self.Cls(*a, **kw)
        self.block = block
        super().__init__(n_inputs=None, name='{}_{}'.format(block.__class__.__name__, id(self)), **kw)
        block.__block__ = self

    def init(self):
        self.block.init()

    def process(self, *xs, meta):
        return [self.block.process(*xs)], meta

    def finish(self):
        self.block.finish()


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

# with reip.Graph() as g:
#     with reip.Task():
#         cam1 = Block(core.Camera(), max_processed=100)
#     with reip.Task():
#         cam2 = Block(core.Camera())

#     with reip.Task():
#         stitch = Block(core.Stitch())(cam1, cam2)
#         filtered = Block(core.MotionFilter())(stitch)
    
#     with reip.Task():  # XXX maybe delete
#         ml = Block(core.ML())(filtered)

#     write_video = Block(core.Write())(filtered)
#     write_ml = Block(core.Write())(ml)


# g.run()
# for b in g.blocks:
#     print(b.status())