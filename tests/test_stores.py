import time
import numpy as np
import reip
import pytest
from remote_func import remote_func
import remoteobj


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

DEFAULT = 'some process context idk'
OTHER_ID = 'adsf'


def keyboard_interrupts(func):
    import functools
    @functools.wraps(func)
    def inner(*a, **kw):
        try:
            return func(*a, **kw)
        except KeyboardInterrupt as e:
            raise RuntimeError("interrupted - now you'll flipping show me. eat my shorts pytest.") from e
    return inner

@pytest.mark.parametrize("task_id,throughput,CustomerCls,PointerCls,StoreCls", [
    (DEFAULT, None, reip.stores.Customer, reip.stores.Pointer, reip.stores.Store),
    (OTHER_ID, 'small', reip.stores.QueueCustomer, reip.stores.SharedPointer, reip.stores.QueueStore),
    (OTHER_ID, 'medium', reip.stores.QueueCustomer, reip.stores.SharedPointer, reip.stores.QueueStore),
    (OTHER_ID, 'large', reip.stores.Customer, reip.stores.SharedPointer, reip.stores.PlasmaStore),
    (OTHER_ID, None, reip.stores.QueueCustomer, reip.stores.SharedPointer, reip.stores.QueueStore),
])
@pytest.mark.parametrize("data_func", [
    (str),
    (int),
    (float),
    (lambda x: [x]),
    (lambda x: {'adsf': x}),
    (lambda x: {x}),
    # (np.array),
    (lambda x: np.array([x])),
    # (lambda x, d=10: np.array([[x]*d]*d)),
])
@keyboard_interrupts
def test_producer(task_id, throughput, CustomerCls, PointerCls, StoreCls, data_func, **kw):
    print(task_id, throughput, CustomerCls, PointerCls, StoreCls, data_func, **kw)
    # get sink
    sink = reip.stores.Producer(100, task_id=DEFAULT)

    # get sources
    if throughput is not None:
        kw['throughput'] = throughput
    kw['task_id'] = task_id
    src0 = sink.gen_source(**kw)
    src1 = sink.gen_source(strategy=reip.Source.Skip, skip=1, **kw)
    src2 = sink.gen_source(strategy=reip.Source.Latest, **kw)
    srcs = [src0, src1, src2]

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

    sink.spawn()

    # build queue inputs
    all_expects1 = [(data_func(i), {"buffer": i}) for i in range(10)]
    all_expects2 = [(data_func(i), {"buffer": i}) for i in range(40, 50)]
    # pre-load
    for x in all_expects1:
        sink.put(x)

    # start remote process
    exps = [get_expects(all_expects1), get_expects(all_expects2)]
    with remoteobj.util.job(run, srcs, exps, threaded_=task_id == sink.task_id, timeout_=3) as p:
        # wait for srcs to catch up
        while srcs[-1].cursor.counter < sink.head.counter:
            time.sleep(1e-2)
            p.raise_any()
        # add second round of sources
        for x in all_expects2:
            sink.put(x)
    sink.join()
