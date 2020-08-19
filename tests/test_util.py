from reip import util
from reip.util import shell



def test_shell():
    # test basic
    o = shell.run('echo 10')
    assert o == ('10\n', '', 'echo 10')

    # test insert and quote
    o = shell.run('echo {}', '10 && echo 15')
    assert o == ('10 && echo 15\n', '', "echo '10 && echo 15'")

    # test insert without quote
    o = shell.run('echo {!r}', '10 && echo 15')
    assert o == ('10\n15\n', '', 'echo 10 && echo 15')

    # test insert many
    o = shell.run('echo {} {b} {a}', 10, a=11, b=15)
    assert o == ('10 15 11\n', '', 'echo 10 15 11')

    # test insert many
    iface = None  # wlan0
    o = shell.run('ping {} 8.8.8.8', dict(I=iface, c=3, q=True))
    assert o.cmd == 'ping -c 3 -q 8.8.8.8'
    assert 'PING 8.8.8.8' in o.out
    assert not o.err


def test_meta():
    maps = [{'a': 5}, {'b': 6}]
    meta = util.Meta({}, *maps)
    # check flat
    assert dict(meta) == {'a': 5, 'b': 6}
    # check update
    meta['c'] = 7
    assert dict(meta) == {'a': 5, 'b': 6, 'c': 7}
    assert meta.maps == [{'c': 7}, {'a': 5}, {'b': 6}]

    # check merging and removing duplicates
    meta2 = util.Meta({'d': 8}, meta, meta)
    assert len(meta2.maps) == len(meta.maps) + 1
    assert meta2.maps == [{'d': 8}, {'c': 7}, {'a': 5}, {'b': 6}]


def test_iters():
    # test basic while
    loop = util.iters.loop()
    assert [x for x, _ in zip(range(10000), loop)]

    # test timed + throttled
    rate, dur = 10, 1
    loop = util.iters.timed(util.iters.throttled(util.iters.loop(), rate), dur)
    assert len(list(loop)) < rate * dur+1


def test_stopwatch():
    pass


def test_remote():
    pass


def test_text():
    pass


def test_misc():
    # # test ensure_dir
    # f = util.adjacent_file(__file__, 'some/nested/file.blah')
    # util.ensure_dir(f)
    # assert os.path.isdir(os.path.dirname(f))

    # test convert to list
    assert util.as_list(5) == [5]
    assert util.as_list('asdf') == ['asdf']
    assert util.as_list((1, 2)) == [1, 2]
    assert util.as_list([1, 2]) == [1, 2]


def test_debug():
    pass
