import time
import reip
from remote_func import remote_func


def get_all_available(src):
    '''Get all available items from a queue.'''
    items = []
    while not src.empty():
        items.append(src.get())
        src.next()
    return items

def run(srcs, expects):
    print("Started")
    print('-'*10)
    for i, expected in enumerate(expects):
        print(f'expected i={i}:')
        for j, (src, exp) in enumerate(zip(srcs, expected)):
            print(f'  src i={j}:')
            avail = get_all_available(src)
            print(f'    {len(exp)} exp. {len(avail)} avail.')
            print(f'    exp: {exp}')
            print(f'    avail: {avail}')
            assert avail == exp
        print('-'*10)
        time.sleep(1)
    print('Done')


def run_test_producer(context_id=True, **kw):
    # get sink
    sink = reip.stores.Producer(100)

    # get sources
    kw['context_id'] = context_id
    src0 = sink.gen_source(**kw)
    src1 = sink.gen_source(strategy=reip.Source.Skip, skip=1, **kw)
    src2 = sink.gen_source(strategy=reip.Source.Latest, **kw)
    srcs = [src0, src1, src2]

    # convert sink data to expected source data
    get_expects = lambda all_expects: [
        all_expects,
        all_expects[1::2],
        all_expects[-1:]
    ]

    # wrap run with a remote process/thread
    remote_run = remote_func(run, threaded=context_id is not sink.context_id)

    sink.spawn()

    # build queue inputs
    all_expects1 = [(str(i), {"buffer": i}) for i in range(10)]
    all_expects2 = [(str(i), {"buffer": i}) for i in range(40, 50)]
    # pre-load
    for x in all_expects1:
        sink.put(x)

    # start remote process
    f = remote_run(srcs, [
        get_expects(all_expects1),
        get_expects(all_expects2),
    ])

    # add second round of sources
    time.sleep(0.8)
    for x in all_expects2:
        sink.put(x)
    time.sleep(0.2)
    f.result()

    sink.join()

def test_producer_threaded():
    print('Threaded:')
    run_test_producer()

def test_producer_process():
    for th in ['small', 'medium', 'large']:
        print(f'Process: Throughput: {th}')
        run_test_producer(context_id='something else', throughput=th)
