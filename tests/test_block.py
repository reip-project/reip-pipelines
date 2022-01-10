import time
import pytest
import reip


def test_connections():
    '''

    - test __call__ with:
        - two multi-sink blocks
        - single-sink block
        - Producer
    - test .to() return value
    - test output stream
    '''
    # test with 0-3 sinks
    inputs = [reip.Block(n_outputs=i) for i in range(4)]
    sink = reip.Producer(10)
    assert all(len(b_in.sinks) == i for i, b_in in enumerate(inputs))
    all_sinks = [s for b in inputs for s in b.sinks] + [sink]
    all_inputs = [*inputs, sink]

    # test that the sources were added correctly
    output = reip.Block(n_inputs=-1)
    assert len(output.sources) == 0
    output(*all_inputs)
    assert [s.source for s in output.sources] == all_sinks

    # test zero sources
    output = reip.Block(n_inputs=0)
    assert len(output.sources) == 0
    with pytest.raises(RuntimeError):
        output(*all_inputs)
    assert len(output.sources) == 0
    output(*all_inputs, ignore_extra=True)
    assert len(output.sources) == 0

    # test that the sources were added correctly
    output = reip.Block(n_inputs=-1)
    assert len(output.sources) == 0
    for inp in inputs:
        inp.to(output, index='append')
    output(sink, index='append')
    print([s.source for s in output.sources])
    assert [s.source for s in output.sources] == all_sinks

    # test a restricted number of sources
    n = 3
    output = reip.Block(n_inputs=n)
    assert output.sources == [None]*n
    output(*all_inputs, ignore_extra=True)
    assert [s.source for s in output.sources] == all_sinks[:n]

    # test too many sources
    output = reip.Block(n_inputs=n)(*all_inputs, ignore_extra=True)
    output.sources.append(sink.gen_source())
    with pytest.raises(RuntimeError):
        output._Block__check_source_connections()

    # test missing sources
    output = reip.Block(n_inputs=-1)(*all_inputs)
    output.sources[0] = None
    with pytest.raises(RuntimeError):
        output._Block__check_source_connections()

    # test missing sources
    with reip.Graph() as g:
        output = reip.Block(max_generated=1, n_inputs=-1, log_level='debug', name='hasjdkfhajfdkh')(*all_inputs)
        output.sources[0] = None
    with pytest.raises(RuntimeError):
        try:
            g.run()
        except Exception as e:
            raise e['hasjdkfhajfdkh'].exc
        g.run()


class Constant(reip.Block):
    n_inputs = 0
    def __init__(self, x, **kw):
        super().__init__(**kw)
        self.x = x

    def process(self, meta):
        return self.x, meta


class Constants(Constant):
    def process(self, meta):
        yield from ((x, meta) for x in self.x)

def test_process_function_returns():
    with reip.Graph() as g:
        out = Constant(5, max_generated=10).output_stream()
    g.run()
    assert list(out.data[0].nowait()) == [5]*10
    with reip.Graph() as g:
        out = Constants([5, 6], max_generated=10).output_stream()
    g.run()
    assert list(out.data[0].nowait()) == [5, 6]*5


def test_init_errors_from_block_in_task():
    with reip.Graph() as g:
        with reip.Task() as t:
            reip.Block(max_generated=10)(reip.Block(name='1234512345'), reip.Block())
    with pytest.raises(RuntimeError, match=r'Sources \[0\] in .+ not connected\.'): # r'Expected \d+ sources'
        try:
            g.run()
            for b in g.iter_blocks(True):
                print(4444, b.name, b._exception)
        except Exception as e:
            print(5555, e.excs)
            raise e['1234512345'].exc



class ErrorBlock(reip.Block):
    def process(self, meta=None):
        print('hi')
        raise RuntimeError()


def block_state_counter(b, state='spawned'):
    b.count = 0
    print(b, type(b))
    print(b.state)
    state = b.state[state]
    @state.add_callback
    def _inc(state, value):
        if value:
            reip.util.print_stack()
            b.count += 1
    return b

def test_handlers():
    with reip.Graph.detached() as g:
        b = reip.Block(max_generated=3, n_inputs=0)
        block_state_counter(b)
    g.run()
    assert b.count == 1
    g.run()
    assert b.count == 2

    # with reip.Graph.detached() as g:
    #     b = ErrorBlock(handlers=reip.util.handlers.retry(3), n_inputs=0, log_level='debug')
    #     block_state_counter(b)
    # with pytest.raises(RuntimeError):
    #     try:
    #         g.run()
    #     finally:
    #         print(g._except)
    # assert b.count == 3


# class BlockPresence(reip.Block):
#     def __init__(self, *a, **kw):
#         super().__init__(*a, n_inputs=None, **kw)
#
#     def process(self, *xs, meta=None):
#         return [None] * len(self.sinks), {self.name: True}
#
#
# def test_zero_sinks():
#     with reip.Graph() as g:
#         inputs = [BlockPresence(n_outputs=i) for i in range(4)]
#         output = reip.Block()(*inputs)
#
#     with g.run_scope():
#         with output.output_stream(duration=0.2) as out_stream:
#             for d, meta in out_stream:
#                 assert set(b.name for b in inputs) == set(meta)
#                 print(meta)
#
#     # with g.run_scope():
#     #     with output.output_stream(duration=0.2):
#     #         for d, meta in out_stream:
#     #             assert set(b.name for b in inputs) == set(meta)
#     #             print(meta)



class StateTester(reip.Block):
    n_inputs = -1

    def _check_state(self, ready=True, running=True, done=False, terminated=False, started=True, error=None):
        assert started is None or self.state.spawned.value == started
        assert ready is None or self.ready == ready
        assert running is None or self.running == running
        assert done is None or self.done == done
        assert terminated is None or self.terminated == terminated
        assert bool(self.error) == (error is not None)
        assert (
            self._exception is None if error is None else
            isinstance(self._exception, error))

    def init(self):
        self._check_state(ready=False)

    # def _do_init(self, *a, **kw):
    #     super()._do_init(*a, **kw)
    #     self._check_state()

    def process(self, *xs, meta):
        self._check_state()
        return xs, meta

    def finish(self):
        self._check_state(ready=False)

    def _main(self, *a, **kw):
        try:
            super()._main(*a, **kw)
        finally:
            self._check_state(ready=False, done=True)

def test_basic_state():
    with reip.Graph() as g:
        tester = StateTester()
    for _ in range(5):
        g.run(duration=0.1, raise_exc=True)




# class ErrorStateTester(StateTester):
#     def process(self, meta):
#         raise RuntimeError()
#
#     def finish(self):
#         self._check_state(error=RuntimeError)
#         del self._except._groups['process']
#         self._except.last = None
#
#     def _do_finish(self, *a, **kw):
#         super()._do_finish(self, *a, **kw)
#         self._check_state(done=True, error=RuntimeError)
#
#
# def test_error_state():
#     with reip.Graph() as g:
#         tester = ErrorStateTester()
#     print(g)
#     for _ in range(5):
#         g.run(duration=0.1, raise_exc=True)



class CloseStateTester(StateTester):
    def process(self, meta):
        self.close()

def test_close_state():
    with reip.Graph() as g:
        tester = CloseStateTester()
    for _ in range(5):
        g.run(duration=0.1, raise_exc=True)



class TerminateStateTester(StateTester):
    def process(self, meta):
        self.terminate()

    def finish(self):
        self._check_state(ready=False, terminated=True)

    def _main(self, *a, **kw):
        try:
            reip.Block._main(self, *a, **kw)
        finally:
            self._check_state(ready=False, done=True, terminated=True)

def test_term_state():
    with reip.Graph() as g:
        tester = TerminateStateTester()
    for _ in range(5):
        g.run(duration=0.1, raise_exc=True)



class PauseStateTester(StateTester):
    def process(self, meta):
        self._check_state(running=None)
        return [], meta

    def finish(self):
        self._check_state(ready=False, running=None)


def test_pause_resume_state():
    with reip.Graph() as g:
        tester = PauseStateTester()

    delay = 0.01
    processed = 0
    for _ in range(5):
        assert tester.processed == processed
        with g.run_scope():
            print(tester, 111)
            assert tester.running == True
            g.wait(duration=delay)
            assert tester.processed > 0

            print(tester, 112)
            tester.pause()
            time.sleep(1e-5)
            processed = tester.processed
            print(tester, 222)
            assert tester.running == False
            g.wait(duration=delay)
            assert tester.processed == processed

            print(tester, 223)
            tester.resume()
            processed = tester.processed
            print(tester, 333)
            assert tester.running == True
            g.wait(duration=delay)
            assert tester.processed > processed
        processed = tester.processed
        tester.raise_exception()
        g.raise_exception()



def test_extra_kw():
    class Block1(reip.Block):
        EXTRA_KW = True
        KW_TO_ATTRS = True
        a = 10
        b = 11

    class Block2(Block1):
        b = 14
        c = 15

    b1 = Block1(a=50, b=51, c=52)
    b2 = Block2(a=50, b=51, c=52)

    assert b1.a == 50
    assert b1.b == 51
    assert not hasattr(b1, 'c')
    assert b2.a == 50
    assert b2.b == 51
    assert b2.c == 52

    assert b1.extra_kw == {'c': 52}
    assert b2.extra_kw == {}



# def test_extra_meta():
#     class A:
#         i = 0
#         def __call__(self, meta=None):
#             self.i += 1
#             return {'z': self.i}

#     with reip.Graph.detached() as g:
#         a = A()
#         block = reip.blocks.Increment(
#             max_generated=10,
#             extra_meta=[{'a': 1}, {'b': 2}, a, {'c': 12}]
#             )
#         out = block.output_stream()
#         assert block._extra_meta == [{'a': 1, 'b': 2}, a, {'c': 12}]
#     print(out)
#     g.run()
#     print(out)

#     metas = [dict(m) for m in list(out.nowait().meta)]
#     assert [dict(m) for m in metas] == [
#         {'a': 1, 'b': 2, 'c': 12, 'z': i+1} for i in range(block.max_generated)
#     ]


def test_prints():
    # test too many sources
    with reip.Graph.detached() as g:
        block = reip.Block(n_inputs=-1)
    with g.run_scope():
        pass
    block.status()
    block.summary()
    block.stats_summary()
