import os
import time
import reip
import reip.blocks as B



#########################
# test blocks/misc.py
#########################

def test_iterator():
    # test iterator
    data = list(range(10))
    with reip.Graph() as g:
        results = B.Iterator(data).output_stream()
    with g.run_scope():
        results = [d for (d,), meta in results]
    assert results == data


def test_interval():
    ALLOWED_INIT_TIME = 0.2
    duration = 1
    interval = 0.1

    with reip.Graph() as g:
        # get the first sink
        block = B.Interval(interval)

    t0 = time.time()
    with g.run_scope():
        with block.output_stream(duration=duration) as out:
            results = list(out)
    # check that the overall time is right
    assert time.time() - t0 < duration + ALLOWED_INIT_TIME
    # check that it returned about the right number of items
    assert duration / interval - 1 <= len(results) <= duration / interval


def test_constant():
    value = 5
    with reip.Graph() as g:
        out = B.Constant(value).output_stream(duration=0.1, max_rate=100)

    with g.run_scope():
        results = set(d for (d,), meta in out)
    assert results == {value}


def test_increment():
    with reip.Graph() as g:
        out = B.Increment(start=10, stop=100, step=10).output_stream()

    with g.run_scope():
        data = [d for (d,), meta in out]
    assert data == list(range(10, 100, 10))


#########################
# test blocks/output.py
#########################


def test_output():
    # generate random data
    # write to csv
    # read csv data
    try:
        N = 100
        with reip.Graph() as g:
            csv_files = B.Increment(N).to(B.Time()).to(B.Csv(
                reip.util.adjacent_file(__file__, '{time}.csv'),
                max_rows=10)).output_stream()
        g.run(raise_exc=True)
        csv_files.close()
        print(csv_files)
        files = [d[0] for d, meta in csv_files]

        assert len(files) == 10

        import csv
        data = []
        for fname in files:
            with open(fname, 'r') as f:
                data.extend(int(d[0]) for d in csv.reader(f))
        assert data == list(range(N))
    finally:
        for fname in files:
            if os.path.isfile(fname):
                os.remove(fname)




#########################
# test blocks/archive.py
#########################


def test_archive():
    # create file
    # compress archive
    # decompress archive
    # check file is the same
    pass


#########################
# test blocks/os_watch.py
#########################


def test_os():
    import reip.blocks.os_watch
    # create file - see if emitted
    # modify file - see if emitted
    # move file - see if emitted
    # delete file - see if emitted
    rel = reip.util.adjacent_file(__file__)
    with reip.Graph() as g:
        created = B.os_watch.Created(relative=rel).to(B.Results())
        modified = B.os_watch.Modified(relative=rel).to(B.Results())
        moved = B.os_watch.Moved(relative=rel).to(B.Results())
        deleted = B.os_watch.Deleted(relative=rel).to(B.Results())

    f_pat = os.path.join(rel, 'test_file_{}.txt')


    fs = [f_pat.format(i) for i in range(5)]
    fs_moved = [f_pat.format(f'moved_{i}') for i in range(len(fs))]
    EVENT_SPACE = 0.2
    with g.run_scope():
        # create
        for fname in fs:
            with open(fname, 'w') as f:
                f.write('')
        time.sleep(EVENT_SPACE)
        # modify
        for fname in fs:
            with open(fname, 'w') as f:
                f.write('modified')
        time.sleep(EVENT_SPACE)
        # move
        for fname, f_mv in zip(fs, fs_moved):
            os.rename(fname, f_mv)
        time.sleep(EVENT_SPACE)
        # delete
        for f_mv in fs_moved:
            os.remove(f_mv)
        time.sleep(EVENT_SPACE)
        # wait
        time.sleep(3)

    # print(created.results)
    # print(modified.results)
    # print(moved.results)
    # print(deleted.results)
    # print(fs, fs_moved)
    assert set(created.results) == set(fs)
    assert set(modified.results) == set(fs) | {rel}
    assert set(moved.results) == set(fs) #set(list(zip(fs, fs_moved)))
    assert set(deleted.results) == set(fs_moved)

#
# def test_audio_features():
#     # load example audio
#     # compute SPL, STFT, ml to ground truth
#     pass
#
#
# def test_microphone():
#     # read from microphone
#     # check shape
#     pass
#
#
# def test_encrypt():
#     # create file
#     # encrypt file
#     # decrypt file
#     # check if file is the same
#     pass
#
#
# def test_buffer():
#     # generate data
#     # check shape
#     # rebuffer
#     # check new shape
#     pass
#
#
def test_shell():
    # run basic command and look at output
    n = 10
    with reip.Graph() as g:
        outputs = B.Increment(n).to(B.Shell('echo {}')).to(B.Results())  # ; echo 16 >&2
    g.run()

    assert len(outputs.results) == n
    assert outputs.results == [str(x) for x in range(len(outputs.results))]


def test_streamer():
    @B.streamer
    def basic_block(stream, x=111):
        assert x > 444
        for i, ((data,), meta) in enumerate(stream):
            assert data == i
            yield [x + data], meta
        yield [0], {}

    n = 10
    x = 555
    with reip.Graph() as g:
        outputs = B.Increment(n).to(basic_block(555)).to(B.Results())  # ; echo 16 >&2
    g.run()

    assert outputs.results == [x + i for i in range(n)] + [0]


def test_process_func():
    @B.process_func
    def basic_block(block, x, meta):
        return [x * 2], {}

    n = 10
    with reip.Graph() as g:
        outputs = B.Increment(n).to(basic_block()).to(B.Results())
    g.run()

    assert outputs.results == [i*2 for i in range(n)]
