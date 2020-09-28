'''

What these tests should guarantee:
 - that graph/task contexts work correctly

'''
import time
from contextlib import contextmanager
import reip
import pytest



class BadBlock(reip.Block):
    def __init__(self, **kw):
        super().__init__(n_source=None, **kw)

    def process(self, meta):
        time.sleep(0.01)
        raise TypeError('youre not my dad !! :p')

class Task(reip.Task):
    def poke(self):
        raise TypeError('go to your room !! >.<')



def test_block_error_in_graph():
    with reip.Graph() as g:
        b = BadBlock(max_processed=10)

    with pytest.raises(TypeError):
        g.run()
    assert b.processed == 0

    with pytest.raises(TypeError):
        with g.run_scope():
            time.sleep(0.02)
    assert b.processed == 0

    g.spawn()
    time.sleep(0.02)
    with pytest.raises(TypeError):
        g.join()
    assert b.processed == 0


def test_block_error_in_task():
    with reip.Task() as g:
        b = BadBlock()

    with pytest.raises(TypeError):
        g.run()

    with pytest.raises(TypeError):
        with g.run_scope():
            time.sleep(0.02)

    g.spawn()
    time.sleep(0.02)
    with pytest.raises(TypeError):
        g.join()


def test_block_error_solo():
    with reip.Graph() as g:
        b = BadBlock(max_processed=10)

    with pytest.raises(TypeError):
        b.run()
    assert b.processed == 0

    with pytest.raises(TypeError):
        with b.run_scope():
            time.sleep(0.02)
    assert b.processed == 0

    b.spawn()
    time.sleep(0.02)
    with pytest.raises(TypeError):
        b.join()
    assert b.processed == 0
