import time
import reip
import reip.blocks as B
import numpy as np

# import pyinstrument

import threading
import multiprocessing as mp

# import logging
# reip.log.setLevel(logging.INFO)

def dbg(cls):
    class cls2(cls):
        def init(self):
            super().init()
            self.log.info(f'{mp.current_process().name}  {threading.current_thread().name}')
    cls2.__name__ = cls.__name__
    return cls2

def statelog(b):
    return lambda s, v: b.log.warning(f'{s} {v}')

def run(throughput='large', duration=5, task=True, max_rate=1000, size=1000):
    with reip.Graph() as g:
        with (reip.Task() if task else reip.Graph()) as t:
            cam = B.Constant(np.random.random((size,size,3)), max_rate=max_rate, name='cam')#.to(B.Debug())
            inbetween = cam.to(reip.Block(name='transformer', max_rate=max_rate), strategy='latest')
        c = reip.Block(name='consumer', max_rate=max_rate)(inbetween, throughput=throughput, strategy='latest')#.to(B.Debug())
    # q = c.sinks[0].gen_source()

    # b = cam
    # b.prof = None
    # def pyi(state, value):
    #     if value:
    #         b.prof = pyinstrument.Profiler()
    #         b.prof.__enter__()
    #     elif b.prof:
    #         b.prof.__exit__()
    #         b.prof.print()

    # cam.state.ready.add_callback(pyi)

    t0 = time.time()
    g.run(duration)
    dt = time.time() - t0
    print('finished run', dt)

    for b in g.iter_blocks():
        print(b.stats_summary())


    files = []

    # print(len(q), 'remaining in queue')
    # while len(q):
    #     # print(len(q))
    #     x = q.get(block=False)
    #     # print(x)
    #     # x, m = x
    #     q.next()
    #     # x = x[0]
    #     # print(type(x), len(x), m)
    #     files.append(x)
    # print(len(files), len(files)/duration)

if __name__ == '__main__':
    import fire
    fire.Fire(run)