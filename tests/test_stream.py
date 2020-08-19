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
        stream.next()

    for i in range(10):
        sink.put((i, {'i': i}))

    for i, ((data,), meta) in enumerate(stream):
        assert data == i
        assert meta['i'] == i
        stream.next()
