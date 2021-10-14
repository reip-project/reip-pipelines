'''

What these tests should guarantee:
 - that graph/task contexts work correctly

'''
import time
import reip
import pytest

class CustomError(Exception):
    pass

class BadInit(reip.Block):
    n_inputs = -1
    def init(self):
        time.sleep(0.01)
        raise CustomError('youre not my dad !! :p')


class BadBlock(reip.Block):
    n_inputs = -1
    def process(self, meta):
        time.sleep(0.01)
        raise CustomError('youre not my dad !! :p')


class BadFinish(reip.Block):
    n_inputs = -1
    def process(self, meta):
        return reip.CLOSE

    def finish(self):
        time.sleep(0.01)
        raise CustomError('youre not my dad !! :p')


class Task(reip.Task):
    def poke(self):
        raise CustomError('go to your room !! >.<')

def agg_generated_count(g):
    return g.generated if isinstance(g, reip.Block) else sum(agg_generated_count(b) for b in g.blocks)

def _test_run_error(g, init=False):
    with pytest.raises(CustomError):
        g.run()
        print(g._except)
        for b in g.blocks:
            print(b._except)
    assert agg_generated_count(g) == 0

    with pytest.raises(CustomError):
        with g.run_scope():
            time.sleep(0.02)
    assert agg_generated_count(g) == 0

    # if init:
    #     with pytest.raises(CustomError):
    #         g.spawn()
    # else:
    #     g.spawn()
    # time.sleep(0.02)
    # with pytest.raises(CustomError):
    #     g.join()
    # assert agg_generated_count(g) == 0

    with pytest.raises(CustomError):
        try:
            g.spawn()
        finally:
            time.sleep(0.02)
            g.join()
    assert agg_generated_count(g) == 0


blk_param = lambda: pytest.mark.parametrize("Block,test_func", [
    (BadBlock, _test_run_error),
    (BadInit, reip.util.partial(_test_run_error, init=True)),
    (BadFinish, _test_run_error),
])

@blk_param()
def test_block_error_in_graph(Block, test_func):
    with reip.Graph() as g:
        Block(max_generated=10)
    test_func(g)

@blk_param()
def test_block_error_in_task(Block, test_func):
    with reip.Task() as g:
        Block(max_generated=10)
    test_func(g)

@blk_param()
def test_block_error_in_task_in_graph(Block, test_func):
    with reip.Graph() as g:
        with reip.Task():
            Block(max_generated=10)
    test_func(g)

@blk_param()
def test_block_error_solo(Block, test_func):
    b = Block(max_generated=10, graph=None)
    test_func(b)
