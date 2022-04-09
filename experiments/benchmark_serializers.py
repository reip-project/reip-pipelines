'''

There are currently 6 different protocols which can be used for pickling. The higher the protocol used, the more recent the version of Python needed to read the pickle produced.

Protocol version 0 is the original “human-readable” protocol and is backwards compatible with earlier versions of Python.
Protocol version 1 is an old binary format which is also compatible with earlier versions of Python.
Protocol version 2 was introduced in Python 2.3. It provides much more efficient pickling of new-style classes. Refer to PEP 307 for information about improvements brought by protocol 2.
Protocol version 3 was added in Python 3.0. It has explicit support for bytes objects and cannot be unpickled by Python 2.x. This was the default protocol in Python 3.0–3.7.
Protocol version 4 was added in Python 3.4. It adds support for very large objects, pickling more kinds of objects, and some data format optimizations. It is the default protocol starting with Python 3.8. Refer to PEP 3154 for information about improvements brought by protocol 4.
Protocol version 5 was added in Python 3.8. It adds support for out-of-band data and speedup for in-band data. Refer to PEP 574 for information about improvements brought by protocol 5.

'''
import time
import pickle
# import pyarrow
import numpy as np


def test_data(s=1000, d=2):
    return 


class Serialize:
    def __init__(self, loads, dumps, limit=None):
        self.loads = loads
        self.dumps = dumps
        self.limit = limit

def Pickler(protocol, **kw):
    if protocol < 3:
        kw.setdefault('limit', -1)
    return Serialize(
        (lambda x: pickle.loads(x)), 
        (lambda x: pickle.dumps(x, protocol=protocol)), 
        **kw)

CANDIDATES = {
    **{f'Pickle - Protocol {p}': Pickler(p) for p in [0, 3, 4, 5]},#
    # 'pyarrow': Serialize(
    #     (lambda x: pyarrow.serialize(x).to_buffer()), 
    #     (lambda x: pyarrow.deserialize(x))),
}


def run(n=100, time_limit=10):
    ds = [
        np.random.random((10, 10, 3)),
        np.random.random((100, 100, 3)),
        np.random.random((1000, 1000, 3)),
        np.random.random((10000, 10000, 3)),
    ]
    limits = [-1, None, None, None]

    for k, ser in CANDIDATES.items(): #ntimes
        print(k)
        print('-'*20)
        for d in ds[:ser.limit]:
            print(d.shape)
            t0 = time.time()
            for i in range(n):
                ser.dumps(d)
                if time.time() - t0 > time_limit: break
            dt = time.time() - t0
            print(f'{(i+1) / dt:.4f} x/s {i+1}x {dt:.4f}s')
            
            db = ser.dumps(d)
            t0 = time.time()
            for i in range(n):
                ser.loads(db)
                if time.time() - t0 > time_limit: break
            dt = time.time() - t0
            print(f'{(i+1) / dt:.4f} x/s {i+1}x {dt:.4f}s')
            print()


if __name__ == '__main__':
    import fire
    fire.Fire()