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
    inputs = [reip.Block(n_sink=i) for i in range(4)]
    sink = reip.Producer(10)
    assert all(len(b_in.sinks) == i for i, b_in in enumerate(inputs))
    all_sinks = sum((b.sinks for b in inputs), []) + [sink]

    # test that the sources were added correctly
    output = reip.Block(n_source=0)
    assert len(output.sources) == 0
    output(*inputs, sink)
    assert [s.source for s in output.sources] == all_sinks

    # test a restricted number of sources
    n = 3
    output = reip.Block(n_source=n)
    assert output.sources == [None]*3
    output(*inputs, sink)
    assert [s.source for s in output.sources] == all_sinks[:n]

    # test too many sources
    output = reip.Block(n_source=n)(*inputs, sink)
    output.sources.append(sink.gen_source())
    with pytest.raises(RuntimeError):
        output._check_source_connections()

    # test missing sources
    output = reip.Block()(*inputs, sink)
    output.sources[0] = None
    with pytest.raises(RuntimeError):
        output._check_source_connections()



# class BlockPresence(reip.Block):
#     def __init__(self, *a, **kw):
#         super().__init__(*a, n_source=None, **kw)
#
#     def process(self, *xs, meta=None):
#         return [None] * len(self.sinks), {self.name: True}
#
#
# def test_zero_sinks():
#     with reip.Graph() as g:
#         inputs = [BlockPresence(n_sink=i) for i in range(4)]
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
    def __init__(self, *a, **kw):
        super().__init__(*a, n_source=None, **kw)

    def _check_state(self, ready=True, running=True, done=False, terminated=False, error=None):
        assert self.ready == ready
        assert self.running == running
        assert self.done == done
        assert self.terminated == terminated
        assert self.error == (error is not None)
        assert (
            self._exception is None if error is None else
            isinstance(self._exception, error))

    def init(self):
        self._check_state(ready=False)

    def _do_init(self, *a, **kw):
        super()._do_init(*a, **kw)
        self._check_state()

    def process(self, *xs, meta):
        self._check_state()
        return xs, meta

    def finish(self):
        self._check_state()

    def _do_finish(self, *a, **kw):
        super()._do_finish(*a, **kw)
        self._check_state(done=True)

def test_basic_state():
    with reip.Graph() as g:
        tester = StateTester()
    for _ in range(5):
        g.run(duration=0.1, raise_exc=True)




class ErrorStateTester(StateTester):
    def process(self, meta):
        raise RuntimeError()

    def finish(self):
        self._check_state(error=RuntimeError)

    def _do_finish(self, *a, **kw):
        super()._do_finish(self, *a, **kw)
        self._check_state(done=True, error=RuntimeError)


def test_error_state():
    with reip.Graph() as g:
        tester = ErrorStateTester()
    print(g)
    for _ in range(5):
        with pytest.raises(RuntimeError):
            g.run(duration=0.1, raise_exc=True)



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
        self._check_state(terminated=True)

    def _do_finish(self, *a, **kw):
        reip.Block._do_finish(self, *a, **kw)
        self._check_state(done=True, terminated=True)

def test_term_state():
    with reip.Graph() as g:
        tester = TerminateStateTester()
    for _ in range(5):
        g.run(duration=0.1, raise_exc=True)



class PauseStateTester(StateTester):
    def process(self, meta):
        self._check_state(running=self.running)
        return [], meta


def test_pause_resume_state():
    with reip.Graph() as g:
        tester = StateTester()

    delay = 0.01
    processed = 0
    for _ in range(5):
        assert tester.processed == processed
        with g.run_scope():
            assert tester.running == True
            g.wait(duration=delay)
            processed = tester.processed
            assert processed > 0

            tester.pause()
            assert tester.running == False
            g.wait(duration=delay)
            assert tester.processed == processed
            processed = tester.processed

            tester.resume()
            assert tester.running == True
            g.wait(duration=delay)
            assert tester.processed > processed
        processed = tester.processed

        g.raise_exception()






def test_prints():
    # test too many sources
    with reip.Graph() as g:
        block = reip.Block(n_source=None)
    with g.run_scope():
        pass
    block.status()
    block.summary()
    block.print_stats()
