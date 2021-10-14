import reip
from reip.util.stream import Stream


def test_stream():
    sink = reip.Producer(100)
    source = sink.gen_source()
    stream = Stream([source]).nowait()

    for i in range(10):
        sink.put((i, {'i': i}))

    for i, ((data,), meta) in enumerate(stream):
        assert data == i
        assert meta['i'] == i

    for i in range(10):
        sink.put((i, {'i': i}))

    for i, ((data,), meta) in enumerate(stream):
        assert data == i
        assert meta['i'] == i


def test_stream_loop():
    sink = reip.Producer(100)
    source = sink.gen_source()
    stream = Stream([source], duration=0.5, max_rate=10, wait=False)

    for i in range(10):
        sink.put((i, {}))
    assert len(list(stream)) <= 5+1


def test_stream_slice():
    sink = reip.Producer(100)
    source = sink.gen_source()
    stream = Stream([source]).nowait()  # don't wait for sources

    for i in range(10):
        sink.put((i, {'i': i}))
    assert list(stream) == [([i], {'i': i}) for i in range(10)]

    for i in range(10):
        sink.put((i, {'i': i}))
    assert list(stream.data) == [[i] for i in range(10)]

    for i in range(10):
        sink.put((i, {'i': i}))
    assert list(stream.meta) == [{'i': i} for i in range(10)]

    # slicing

    sink2 = reip.Producer(100)
    source2 = sink2.gen_source()
    stream = Stream([source, source2]).nowait()

    for i in range(10):
        sink.put((i, {'i': i}))
        sink2.put((i+3, {'j': i+3}))
    assert list(stream) == [([i, i+3], {'i': i, 'j': i+3}) for i in range(10)]

    for i in range(10):
        sink.put((i, {'i': i}))
        sink2.put((i+3, {'j': i+3}))
    assert list(stream.data[0]) == [i for i in range(10)]
    assert list(stream.data[1]) == [i+3 for i in range(10)]

    for i in range(10):
        sink.put((i, {'i': i}))
        sink2.put((i+3, {'j': i+3}))
    assert list(stream[0]) == [(i, {'i': i}) for i in range(10)]
    assert list(stream[1]) == [(i+3, {'j': i+3}) for i in range(10)]
