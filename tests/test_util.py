import os
import re
import time
import multiprocessing as mp

from reip import util
from reip.util import shell, remote, text


ROOT = os.path.dirname(__file__)


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
    sw = util.Stopwatch()

    check = lambda t, expected, tol=1.1: expected <= t <= expected * tol

    sw.tick()
    with sw():
        with sw('asdf'):
            time.sleep(0.1)

        with sw('asdf'):
            time.sleep(0.1)

        sw.tick('asdf')
        time.sleep(0.1)
        sw.tock('asdf')

        with sw('zxcv'):
            time.sleep(0.1)

        sw.tick('qqqq')
        sw.notock('qqqq')

    assert check(sw.avg('asdf'), 0.1)
    assert check(sw.total('asdf'), 0.3)
    assert check(sw.avg('zxcv'), 0.1)
    assert check(sw.total('zxcv'), 0.1)
    assert 'qqqq' not in sw._ticks and sw.total('qqqq') == 0



class ObjectA:
    x = 10
    term = False
    def __init__(self):
        self.remote = remote.RemoteProxy(self)

    def __str__(self):
        return f'<A x={self.x} terminated={self.term}>'

    def asdf(self):
        self.x *= 2
        return self

    @property
    def zxcv(self):
        return self.x / 5.

    def terminate(self):
        self.term = True
        return self

    def start(self):
        self.term = False
        return self

class ObjectB(ObjectA):
    @property
    def zxcv(self):
        return self.x / 10.

def _run_remote(obj, event):  # some remote job
    with obj.remote:
        while not event.is_set():
            obj.remote.poll()
            time.sleep(0.0001)


def test_remote():
    obj = ObjectB()
    event = mp.Event()
    p = mp.Process(target=_run_remote, args=(obj, event), daemon=True)
    p.start()
    while not obj.remote.listening and p.is_alive():
        time.sleep(1e-2)

    # attribute access
    assert obj.x == 10
    assert obj.remote.x.retrieve() == 10

    # local update
    obj.asdf()
    assert obj.x == 20
    assert obj.remote.x.retrieve() == 10

    # remote update
    obj.remote.asdf()
    assert obj.x == 20
    assert obj.remote.x.retrieve() == 20

    # remote property
    assert obj.zxcv == 2.
    assert obj.remote.zxcv.retrieve() == 2.

    assert super(type(obj), obj).zxcv == 4.
    assert obj.remote.super.zxcv.retrieve() == 4.

    # local terminate
    obj.terminate()
    assert obj.remote.term.retrieve() == False
    assert obj.term == True
    obj.start()
    assert obj.remote.term.retrieve() == False
    assert obj.term == False

    # remote terminate
    obj.remote.terminate()
    assert obj.remote.term.retrieve() == True
    assert obj.term == False
    obj.remote.start()
    assert obj.remote.term.retrieve() == False
    assert obj.term == False

    assert p.is_alive()
    event.set()
    p.join()
    assert not obj.remote.listening


def test_text():
    prep = lambda t: text.strip_each_line(text.striplines(t)).rstrip().replace('\t', ' '*4)
    inspect = lambda *xs: print(text.block_text(*xs, *(repr(x) for x in xs), div='----'))

    original = prep('''
asdf

asdfsadf
    asdf
    ''')
    indented = prep('''
    asdf

    asdfsadf
        asdf
    ''')
    # inspect(original, indented)
    # test indent
    assert text.strip_each_line(text.indent(original)) == indented
    assert text.trim_indent(indented) == original
    assert text.strip_each_line(text.tabindent(original.replace(' '*4, '\t'))) == indented.replace(' '*4, '\t')

    assert text.striplines('\n'*3 + indented + '\n'*3) == indented

    # test commenting
    commented = prep('''
# asdf
#
# asdfsadf
#     asdf
    ''')

    assert text.strip_each_line(text.comment(original)) == commented
    assert text.strip_each_line(text.comment(original, ch='//')) == commented.replace('#', '//')

    # test block text
    block_text = prep('''
********************
* asdf
*
* asdfsadf
*     asdf
*
* hello
********************
    ''')
    assert text.strip_each_line(text.block_text(original, '', 'hello')) == block_text

    # test line and block
    assert text.l_('asdf', 5, 5) == 'asdf 5 5'
    assert text.b_('asdf', (5, 6, 7, 8), 5) == '''
asdf
5 6 7 8
5
    '''.strip()

    # text fixed width format
    assert text.fw_('asdf', w=10) == 'asdf      '

    # test table
    assert text.strip_each_line(text.tbl(
        ('asdf', 6, 7, 'asdf'),
        (5, 6, 7, 8),
        (5, 'asdf', 7, 'asdf'))) == '''
asdf  6     7  asdf
5     6     7  8
5     asdf  7  asdf
    '''.strip()

    # test colors
    assert text.red('a b c') == '\033[91ma b c\033[0m'
    assert text.blue('a b c') == '\033[94ma b c\033[0m'
    assert text.green('a b c') == '\033[92ma b c\033[0m'
    assert text.yellow('a b c') == '\033[93ma b c\033[0m'
    assert text.bold('a b c') == '\033[1ma b c\033[0m'
    assert text.underline('a b c') == '\033[4ma b c\033[0m'


def test_misc():
    assert util.adjacent_file(__file__, 'some/nested/file.blah') == os.path.abspath(os.path.join(ROOT, 'some/nested/file.blah'))
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
    FNAME = os.path.basename(__file__)
    def short(*a, **kw):
        def ddd():
            return util.short_stack(*a, **kw)
        return ddd()

    stack = 'ddd', 'short', 'test_debug'

    assert short(n=3) == ' << '.join(stack)
    assert short(FNAME) == ' << '.join(stack)
    assert re.match(
        ' << '.join(f'{f} \\({FNAME}:\\d+\\)' for f in stack),
        short(FNAME, file=True)
    )

    def block(*a, **kw):
        def ddd():
            return util.block_stack(*a, **kw)
        return ddd()

#     star = '(\\\\x1b\\[93m\\*\\\\x1b\\[0m)'
#     block_patt = '''
# {star}+
# {star} asdf
# {star} ddd \\d+ {__file__}
# {star}
# {star} block       \\d+  {__file__}  >>> return ddd\\(\\)
# {star} test_debug  \\d+  {__file__}  >>> .*
# {star}+
#     '''.strip().format(__file__=__file__, star=star).replace('\n', '\\s*').replace('/', '\\/')
#     print(block('asdf', FNAME))
#     print(repr(block('asdf', FNAME)))
    # print(block_patt)
    # assert re.match(block_patt, block('asdf', FNAME))

    txt = block('asdf', FNAME)
    assert all(x in txt for x in (
        'asdf', __file__, 'block', 'ddd',
        'test_debug', 'return ddd()'))


# def test_background_process():
#     cmd = 'watch ls'
#     server = util.BackgroundServer(cmd, 'watch')
#     assert not server.is_alive
#     with server:
#         assert server.is_alive
#         assert len(server.clients) == 1
#
#         server2 = util.BackgroundServer(cmd, 'watch')
#         assert server.is_alive
#         with server2:
#             assert server2.is_alive
#             assert len(server.clients) == 2
#
#             assert server.clients == server2.clients
#             assert server._pid_dir == server2._pid_dir
#             assert server._pid_file != server2._pid_file
#
#         assert server2.is_alive
#         assert server.is_alive
#         assert len(server.clients) == 1
#     assert not server.is_alive
#     assert len(server.clients) == 0
