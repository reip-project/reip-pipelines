import time
import reip
import pytest
from remote_func import remote_func


def get_all_available(src, n=None):
    '''Get all available items from a queue.'''
    items = []
    while not (n is not None and len(items) == n or src.empty()):
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
            avail = get_all_available(src, n=len(exp))
            print(f'    {len(exp)} exp. {len(avail)} avail.')
            print(f'    exp: {exp}')
            print(f'    avail: {avail}')
            assert avail == exp
        print('-'*10)
        time.sleep(0.5)
    print('Done')


def run_test_producer(task_id='some process context idk',
                      CustomerCls=reip.stores.Customer,
                      PointerCls=reip.stores.Pointer,
                      StoreCls=reip.stores.BaseStore, **kw):
    # get sink
    sink = reip.stores.Producer(100, task_id='some process context idk')

    # get sources
    kw['task_id'] = task_id
    src0 = sink.gen_source(**kw)
    src1 = sink.gen_source(strategy=reip.Source.Skip, skip=1, **kw)
    src2 = sink.gen_source(strategy=reip.Source.Latest, **kw)
    srcs = [src0, src1, src2]

    print(srcs, CustomerCls, PointerCls)
    print([s.cursor for s in srcs])
    print([s.source.head for s in srcs])
    print([s.source.tail for s in srcs])
    if CustomerCls is not None:
        assert all(isinstance(s, CustomerCls) for s in srcs)
    if PointerCls is not None:
        assert all(
            isinstance(s.cursor, PointerCls) and
            isinstance(s.source.head, PointerCls) and
            isinstance(s.source.tail, PointerCls)
            for s in srcs)
    if StoreCls is not None:
        assert all(isinstance(s.store, StoreCls) for s in srcs)

    # convert sink data to expected source data
    get_expects = lambda all_expects: [
        all_expects,
        all_expects[1::2],
        all_expects[-1:]
    ]

    # wrap run with a remote process/thread
    print('threaded', task_id is not sink.task_id)
    remote_run = remote_func(run, threaded=task_id == sink.task_id)

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

    # wait for srcs to catch up
    while srcs[-1].cursor.counter < sink.head.counter:
        time.sleep(1e-3)
    # add second round of sources
    for x in all_expects2:
        sink.put(x)

    f.result()
    sink.join()

def test_producer_threaded():
    print('Threaded:')
    run_test_producer(
        CustomerCls=reip.stores.Customer, StoreCls=reip.stores.Store,
        PointerCls=reip.stores.Pointer,
    )


@pytest.mark.parametrize("throughput,CustomerCls,StoreCls", [
    ('small', reip.stores.QueueCustomer, reip.stores.ClientStore),
    ('medium', reip.stores.QueueCustomer, reip.stores.ClientStore),
    ('large', reip.stores.Customer, reip.stores.PlasmaStore)
])
def test_producer_process(throughput, CustomerCls, StoreCls):
    for th in ['small', 'medium', 'large']:
        print(f'Process: Throughput: {th}')
        run_test_producer(
            task_id='something else',
            CustomerCls=CustomerCls, StoreCls=StoreCls,
            PointerCls=reip.stores.SharedPointer,
            throughput=throughput)