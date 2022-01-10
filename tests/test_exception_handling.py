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
        self.close()

    def finish(self):
        time.sleep(0.01)
        raise CustomError('youre not my dad !! :p')


class Task(reip.Task):
    def poke(self):
        raise CustomError('go to your room !! >.<')

def agg_generated_count(g):
    return g.generated if isinstance(g, reip.Block) else sum(agg_generated_count(b) for b in g.blocks)

def _test_run_error(g, init=False):
    # with pytest.raises(CustomError):
    try:
        g.run()
        print(g._except)
        for b in g.blocks:
            print(b._except)
    except reip.exceptions.GraphException as e:
        # XXX AHHHHHH WTF How to handle this ??????????????????
        print(1,[type(ei).__name__ for ei in e])
        print(1,[ei.__dict__ for ei in e])
        print(2,[type(ei.exc if isinstance(ei, reip.exceptions.SafeException) else ei).__name__ for ei in e])
        # assert any(ei for ei in e if (isinstance(ei.exc, CustomError) if isinstance(ei, reip.exceptions.SafeException) else isinstance(ei, CustomError)))
        assert any(ei for ei in e if isinstance(ei, CustomError))
    assert agg_generated_count(g) == 0

    # with pytest.raises(CustomError):
    try:
        with g.run_scope():
            time.sleep(0.02)
    except reip.exceptions.GraphException as e:
        print(1,[type(ei).__name__ for ei in e])
        print(2,[type(ei.exc if isinstance(ei, reip.exceptions.SafeException) else ei).__name__ for ei in e])
        assert any(ei for ei in e if isinstance(ei, CustomError))
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

    # with pytest.raises(CustomError):
    try:
        try:
            g.spawn()
        finally:
            time.sleep(0.02)
            g.join()
    except reip.exceptions.GraphException as e:
        print(1,[type(ei).__name__ for ei in e])
        print(2,[type(ei.exc if isinstance(ei, reip.exceptions.SafeException) else ei).__name__ for ei in e])
        assert any(ei for ei in e if isinstance(ei, CustomError))
                
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
