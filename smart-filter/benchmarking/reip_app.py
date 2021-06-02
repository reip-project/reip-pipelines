import functools
import reip
import base_app

reip.Block.KW_TO_ATTRS = True


#class Graph(reip.Graph):
#    def __init__(self, name_=None, *a, name=None, **kw):
#        super().__init__(*a, name=base_app.auto_name(self, name=name_ or name), **kw)

Graph = reip.Graph
Task = reip.Task
#class Task(reip.Task):
#    def __init__(self, name_, *a, name=None, **kw):
#        super().__init__(*a, name=base_app.auto_name(self, name=name_ or name), **kw)


class BlocksModule(base_app.BlocksModule):
    def _make_item(self, c, cls):
        if issubclass(c, reip.Block):
            return c
        return super()._make_item(c, cls)

class Block(reip.Block):  # this class is only used for non-reip blocks that implement init/process/finish
    Cls = base_app.CoreBlock
    Graph = Graph
    Task = Task
    wrap_blocks = classmethod(base_app.wrap_blocks)
    Module = BlocksModule

    def __init__(self, *a, block=None, n_inputs=None, name=None, **kw):
        # rename the block class name
        if block is not None or self.Cls.__class__ is not base_app.CoreBlock:
            self.__class__ = type(
                    getattr(block, 'name', None) or block.__class__.__name__ 
                    if block is not None else 
                    self.Cls.__name__, 
                    (self.__class__,), {})
        super().__init__(n_inputs=n_inputs, name=name, extra_kw=True, **kw)
        if block is None:
            block = self.Cls(*a, **self.extra_kw)
        self.block = block
        block.__block__ = self
        block.log = self.log
        self.max_rate = getattr(block, 'max_rate', None) or self.max_rate

    def init(self):
        self.block.init()

    def process(self, *xs, meta):
        return self.block.process(*xs, meta=meta)
        #return [self.block.process(*xs)], meta  # originally I was going to simplify by not using meta, but since we're using existing reip blocks

    def finish(self):
        self.block.finish()


B = base_app.example(Block)
test = functools.partial(base_app.test, B=B)

if __name__ == '__main__':
    import fire
    fire.Fire(test)

