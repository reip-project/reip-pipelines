import pytest
import reip
import reip.blocks as B


@reip.helpers.asblock(single_output=True, meta=False)
def simple(x):
    return x*2

@reip.helpers.asblock(single_output=True, meta=False)
def simple_extra(x, a=1):
    return x*a

@reip.helpers.asblock(single_output=True)
def simple_meta(x, meta):
    return x*2, meta

@reip.helpers.asblock(meta=False)
def multi(x):
    return [x*2]

@reip.helpers.asblock()
def multi_meta(x, meta):
    return [x*2], meta

@reip.helpers.asblock(context=True)
def context():
    def inner(x, meta):
        return [x*2], meta
    yield inner

@reip.helpers.asblock(context=True, self=True)
def context_self(self):
    def inner(x, meta):
        return [x*2, x*4], meta
    yield inner

@reip.helpers.asblock(single_output=True, meta=False, self=True)
def simple_self(self, x):
    return x*2


@pytest.mark.parametrize("block_func", (
    simple,
    simple_meta,
    reip.util.partial(simple_extra, a=2),
    multi,
    multi_meta,
    context,
    context_self,
    simple_self
))
def test_asblock(block_func, n=10):
    with reip.Graph() as g:
        out = B.Increment(n).to(block_func()).output_stream().nowait()  # .to(B.Debug(blk.__name__))
    g.run()
    x = list(out.nowait())
    assert x == [([i*2], {}) for i in range(n)]
