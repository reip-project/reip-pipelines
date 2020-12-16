'''

What these tests should guarantee:
 - that graph/task contexts work correctly

'''
import time
import reip
import pytest



class BadInit(reip.Block):
    def __init__(self, **kw):
        super().__init__(n_inputs=None, **kw)

    def init(self):
        time.sleep(0.01)
        raise TypeError('youre not my dad !! :p')


class BadBlock(reip.Block):
    def __init__(self, **kw):
        super().__init__(n_inputs=None, **kw)

    def process(self, meta):
        time.sleep(0.01)
        raise TypeError('youre not my dad !! :p')


class BadFinish(reip.Block):
    def __init__(self, **kw):
        super().__init__(n_inputs=None, **kw)

    def process(self, meta):
        return reip.CLOSE

    def finish(self):
        time.sleep(0.01)
        raise TypeError('youre not my dad !! :p')


class Task(reip.Task):
    def poke(self):
        raise TypeError('go to your room !! >.<')

def agg_processed(g):
    return g.processed if isinstance(g, reip.Block) else sum(agg_processed(b) for b in g.blocks)

def _test_run_error(g, init=False):
    with pytest.raises(TypeError):
        g.run()
    assert agg_processed(g) == 0

    with pytest.raises(TypeError):
        with g.run_scope():
            time.sleep(0.02)
    assert agg_processed(g) == 0

    # if init:
    #     with pytest.raises(TypeError):
    #         g.spawn()
    # else:
    #     g.spawn()
    # time.sleep(0.02)
    # with pytest.raises(TypeError):
    #     g.join()
    # assert agg_processed(g) == 0

    with pytest.raises(TypeError):
        try:
            g.spawn()
        finally:
            time.sleep(0.02)
            g.join()
    assert agg_processed(g) == 0


blk_param = lambda: pytest.mark.parametrize("Block,test_func", [
    (BadBlock, _test_run_error),
    (BadInit, reip.util.partial(_test_run_error, init=True)),
    (BadFinish, _test_run_error),
])

@blk_param()
def test_block_error_in_graph(Block, test_func):
    with reip.Graph() as g:
        Block(max_processed=10)
    test_func(g)

@blk_param()
def test_block_error_in_task(Block, test_func):
    with reip.Task() as g:
        Block(max_processed=10)
    test_func(g)

@blk_param()
def test_block_error_in_task_in_graph(Block, test_func):
    with reip.Graph() as g:
        with reip.Task():
            Block(max_processed=10)
    test_func(g)

@blk_param()
def test_block_error_solo(Block, test_func):
    b = Block(max_processed=10, graph=None)
    test_func(b)
