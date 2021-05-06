import os
import time
import reip
import reip.blocks as B
import reip.blocks.encrypt



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
    ALLOWED_INIT_TIME = 0.3
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


# def test_sync(delays=(0.05, 0.05, 0.08, 0.09, 0.01), interval=0.2):
#     with reip.Graph() as g:
#         sink = reip.Producer()
#         delay_sink = reip.Producer()
#         B.ControlledDelay()(delay_sink)
#         b1 = .to(reip.Block())
#         b2 = B.Interval(interval, initial=interval/2)(sink).to(reip.Block())
#
#     for i in range(10):
#         for x in delays:
#             sink.put(((x, i), {}))
#             delay_sink.put((x, meta))
#
#     with g.run_scope():
#         while len(sink):


#########################
# test blocks/output.py
#########################


def test_output(tmp_path):
    # generate random data
    # write to csv
    # read csv data
    N = 100
    with reip.Graph() as g:
        csv_files = B.Increment(N).to(B.Time()).to(B.Csv(
            tmp_path / '{time}.csv', max_rows=10)).output_stream()
    g.run(raise_exc=True)
    print(csv_files)
    files = [d[0] for d, meta in csv_files.nowait()]

    assert len(files) == 10

    import csv
    data = []
    for fname in files:
        with open(fname, 'r') as f:
            data.extend(int(d[0]) for d in csv.reader(f))
    assert data == list(range(N))


def test_interleave():
    with reip.Graph.detached() as g:
        out = B.Interleave()(B.Increment(10), B.Increment(10, 20), B.Increment(20, 30)).output_stream()
    g.run()
    x = set(out.data[0].nowait())
    print(x)
    assert x == set(range(30))


def test_separate():
    with reip.Graph() as g:
        out = B.Separate([
            (lambda x, meta: x < 10),
            (lambda x, meta: x < 15),
        ])(B.Increment(20)).output_stream()
    g.run()
    for b in g.blocks:
        print(b, b._except)
    x = list(out.data.nowait())
    print(x)
    a, b = [reip.util.filter_none(x) for x in zip(*x)]
    assert (a, b) == (list(range(10)), list(range(10, 15)))


def test_gather():
    N, group = 20, 5
    with reip.Graph() as g:
        out = B.Gather(group, reduce=sum)(B.Increment(N)).output_stream()
    g.run()
    x = list(out.data[0].nowait())
    print(x)
    assert x == [sum(range(i, i+group)) for i in range(0, N, group)]


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


def test_os(tmp_path):
    import reip.blocks.os_watch
    # create file - see if emitted
    # modify file - see if emitted
    # move file - see if emitted
    # delete file - see if emitted
    rel = str(tmp_path)
    with reip.Graph() as g:
        globbed = B.Glob(os.path.join(rel, '**/*'), recursive=True).output_stream().data[0].nowait()
        created = B.os_watch.Created(path=rel).output_stream().data[0].nowait()
        modified = B.os_watch.Modified(path=rel).output_stream().data[0].nowait()
        moved = B.os_watch.Moved(path=rel).output_stream().data[0].nowait()
        deleted = B.os_watch.Deleted(path=rel).output_stream().data[0].nowait()

    f_pat = str(tmp_path / 'test_file_{}.txt')


    fs = [f_pat.format(i) for i in range(5)]
    fs_moved = [f_pat.format(f'moved_{i}') for i in range(len(fs))]
    OP_SPACE = 0.01
    EVENT_SPACE = 0.1
    with g.run_scope():
        # create
        for fname in fs:
            with open(fname, 'w') as f:
                f.write('original')
            time.sleep(OP_SPACE)
        time.sleep(EVENT_SPACE)
        # modify
        for fname in fs:
            with open(fname, 'w') as f:
                f.write('modified')
            time.sleep(OP_SPACE)
        time.sleep(EVENT_SPACE)
        # move
        for fname, f_mv in zip(fs, fs_moved):
            os.rename(fname, f_mv)
            time.sleep(OP_SPACE)
        time.sleep(EVENT_SPACE)
        # delete
        for f_mv in fs_moved:
            os.remove(f_mv)
            time.sleep(OP_SPACE)
        time.sleep(EVENT_SPACE)
        # wait
        time.sleep(EVENT_SPACE)

    globbed = set(globbed)
    created = set(created)
    modified = set(modified)
    moved = set(moved)
    deleted = set(deleted)
    # print('globbed', globbed)
    # print('created', created)
    # print('modified', modified)
    # print('moved', moved)
    # print('deleted', deleted)
    # print('fs', fs)
    # print('fs_moved', fs_moved)
    moved_misassigned = created - set(fs)
    assert globbed == set(fs) | set(fs_moved)
    assert created >= set(fs) and moved_misassigned <= set(fs_moved)
    assert modified == set(fs) | {rel}
    assert moved == set(fs) #set(list(zip(fs, fs_moved)))
    assert deleted == set(fs_moved)

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


def test_encrypt(tmp_path):
    # create file
    # encrypt file
    # decrypt file
    # check if file is the same
    content = 'some content {} !!!'

    with reip.Graph() as g:
        priv, pub = B.encrypt.create_rsa(tmp_path / 'encrypt_rsa')

        inc = B.Increment(10, max_rate=10)
        txtfile = B.dummy.TextFile(content, tmp_path / 'testfile{}.txt')(inc)
        encrypted = B.encrypt.TwoStageEncrypt(
            tmp_path / 'encrypted/{name}.enc.tar.gz', pub)(txtfile)
        decrypted = B.encrypt.TwoStageDecrypt(
            tmp_path / 'decrypted/{name}.txt', priv)(encrypted)

    with g.run_scope():
        inp = txtfile.output_stream()
        out = decrypted.output_stream()
        with inp, out:
            for ((fin,), m_in), ((fout,), m_out) in zip(inp, out):
                with open(fin, 'r') as f:
                    in_content = f.read()
                with open(fout, 'r') as f:
                    out_content = f.read()
                assert in_content == out_content
                print(fin, fout, in_content, out_content)


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
        out = B.Increment(n).to(B.Shell('echo {}')).output_stream()  # ; echo 16 >&2
    g.run()

    x = list(out.data[0].nowait())
    assert len(x) == n
    assert x == [str(i) for i in range(len(x))]


# def test_streamer():
#     @B.streamer
#     def basic_block(stream, x=111):
#         assert x > 444
#         for i, ((data,), meta) in enumerate(stream):
#             assert data == i
#             yield [x + data], meta
#         yield [0], {}
#
#     n = 10
#     x = 555
#     with reip.Graph() as g:
#         outputs = B.Increment(n).to(basic_block(555)).to(B.Results())  # ; echo 16 >&2
#     g.run()
#
#     assert outputs.results == [x + i for i in range(n)] + [0]


# def test_context_func():
#     class A:
#         init = finish = False
#     @B.context_func
#     def basic_block():
#         try:
#             A.init = True
#             def process(x, meta):
#                 return [x * 2], {}
#             yield process
#         finally:
#             A.finish = True
#     n = 10
#     with reip.Graph() as g:
#         outs = B.Increment(n).to(basic_block()).output_stream().data[0]
#     g.run()

#     outs = list(outs.nowait())
#     assert outs == [i*2 for i in range(n)]
#     assert A.init
#     assert A.finish


# def test_lambda_block():
#     @B.process_func
#     def basic_block(block, x, meta):
#         return [x * 2], {}

#     n = 10
#     with reip.Graph() as g:
#         outs = B.Increment(n).to(basic_block()).output_stream().data[0]
#     g.run()

#     outs = list(outs.nowait())
#     assert outs == [i*2 for i in range(n)]
