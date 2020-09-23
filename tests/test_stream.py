import reip


def test_stream():
    sink = reip.Producer(100)
    source = sink.gen_source()
    stream = reip.Stream([source])
    stream.close()  # don't wait for sources

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
    stream = reip.Stream([source], duration=0.5, max_rate=10)
    stream.close()  # don't wait for sources

    for i in range(10):
        sink.put((i, {}))
    assert len(list(stream)) <= 5
