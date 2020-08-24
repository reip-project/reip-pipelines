import os
import time
import reip
import reip.blocks as B



def test_misc():
    data = list(range(10))
    with reip.Graph() as g:
        results = reip.Stream.from_block(B.Iterator(data))

    with g.run_scope():
        assert list(results) == data


def test_output():
    # generate random data
    # write to csv
    # read csv data
    pass


def test_archive():
    # create file
    # compress archive
    # decompress archive
    # check file is the same
    pass


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
    EVENT_SPACE = 0.4
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
    with reip.Graph() as g:
        outputs = B.Interval(0.1).to(B.Shell('echo {}')).to(B.Results())  # ; echo 16 >&2
    g.run(duration=1)

    assert 1 < len(outputs.results) < 12  # don't know precisely
    assert outputs.results == [str(x) for x in range(len(outputs.results))]
    assert [m['index'] for m in outputs.meta] == [i for i in range(len(outputs.meta))]

#
# def test_streamer():
#     pass
