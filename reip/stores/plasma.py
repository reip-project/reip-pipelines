import os
import time
import numpy as np
import pyarrow as pa
import pyarrow.plasma as plasma
from .base import BaseStore
from .pointers import SharedPointer


def get_plasma_path():
    # import ray
    # plasma_socket = plasma_socket or ray.nodes()[0]['ObjectStoreSocketName']
    return os.path.join(os.getenv('TMPDIR'), 'plasma')

# def start_plasma(plasma_socket=None, plasma_store_memory=1e9):
#     import subprocess
#     command = [
#         'plasma_store',
#         '-s', plasma_socket or get_plasma_path(),
#         '-m', str(int(plasma_store_memory))]
#     print('Starting plasma server...', command)
#     proc = subprocess.Popen(command, stdout=None, stderr=None, shell=False)
#     time.sleep(0.5)
#     return proc
#
#
# def connect_to_plasma(plasma_socket=None, **kw):
#     plasma_socket = plasma_socket or get_plasma_path()
#     client = None #plasma.connect(plasma_dir)
#     if client is None:
#         # if getattr(connect_to_plasma, 'proc', None) is None:
#         #     connect_to_plasma.proc = start_plasma(plasma_socket, **kw)
#
#         client = plasma.connect(plasma_socket)
#     return client



def random_object_id():
    return plasma.ObjectID(np.random.bytes(20))

def random_unique_object_id(existing):
    while True:
        id = random_object_id()
        if id not in existing:
            return id

def n_random_unique_object_ids(client, size=10):
    existing_ids = set(client.list())
    return [
        random_unique_object_id(existing_ids)
        for i in range(size)]


class PlasmaStore(BaseStore):
    Pointer = SharedPointer
    def __init__(self, size, plasma_socket=None):
        self._plasma_socket_name = plasma_socket or get_plasma_path()
        self.client = plasma.connect(self._plasma_socket_name)
        self.ids = n_random_unique_object_ids(self.client, size)
        self.size = size

    _refreshed = False
    def refresh(self):  # TODO: HOW TO CALL THIS WHEN FORKING ???
        self.client = plasma.connect(self._plasma_socket_name)

    def __len__(self):
        return len(self.client.list())

    def put(self, data, meta=None, id=None):
        return save_both(self.client, data, meta or {}, id=self.ids[id])

    def get(self, id):
        if not self._refreshed:
            self.refresh()
            self._refreshed = True
        return load_both(self.client, self.ids[id])

    def delete(self, ids):
        self.client.delete([self.ids[id] for id in ids])


def save_both(client, data, meta=None, id=None):
    # t0 = time.time()
    # print("Saving data with meta...")
    if meta is None:
        meta = {}

    if data is None:
        meta["type"] = "void"
        object_size = 0
    elif isinstance(data, str):
        meta["type"] = "string"
        data = data.encode("utf-8")
        object_size = len(data)
    elif isinstance(data, np.ndarray):
        meta["type"] = "array"
        tensor = pa.Tensor.from_numpy(data)
        object_size = pa.ipc.get_tensor_size(tensor)
    else:
        raise ValueError("Unsupported data type")

    meta = pa.serialize(meta).to_buffer().to_pybytes()

    object_id = id or random_object_id()

    buf = client.create(object_id, object_size, metadata=meta)
    stream = pa.FixedSizeBufferWriter(buf)
    if isinstance(data, bytes):
        stream.write(data)
    elif data is not None:
        stream.set_memcopy_threads(4)
        pa.ipc.write_tensor(tensor, stream)
    client.seal(object_id)

    # print("Saving data with meta took", time.time() - t0)
    return object_id


def load_both(client, id):
    # t0 = time.time()
    # print("Loading data with meta...")

    meta, data = client.get_buffers([id], timeout_ms=1, with_meta=True)[0]
    meta = pa.deserialize(meta)

    if meta["type"] == "void":
        data = None
    elif meta["type"] == "string":
        data = data.to_pybytes().decode("utf-8")
    elif meta["type"] == "array":
        reader = pa.BufferReader(data)
        tensor = pa.ipc.read_tensor(reader)
        data = tensor.to_numpy()
    else:
        raise ValueError("Unsupported data type", meta["type"])

    # print("Loading data with meta took", time.time() - t0)
    return data, meta


def test():
    print(get_plasma_path())
    client = plasma.connect(get_plasma_path())
    print(client.store_capacity())
    print(client.list())
    client.delete(client.list())
    print(client.list())

    print("Generating...")
    data = np.ones(1 * 10 ** 4, dtype=np.uint8)
    # data = "Hello"
    # data = None
    print("Done")

    # id = save_data(client, data)
    # data2 = load_data(client, id)
    # print(data2)
    # client.delete([id])

    meta = {"Foo": 10}

    # id2 = save_meta(client, meta)
    # meta2 = load_meta(client, id2)
    # print(meta2)

    id3 = save_both(client, data, meta)
    data3, meta3 = load_both(client, id3)
    print(data3, meta3)


def test2():
    store = Store()
    for i in range(5):
        print('-'*10, i)
        data = np.ones(1 * 10 ** 4, dtype=np.uint8)
        meta = {"Foo": 10}

        id = store.put(data, meta)
        data2, meta2 = store.get(id)
        print(id, data2, meta2)


if __name__ == '__main__':
    # test()
    test2()
    exit(0)

    client = plasma.connect(get_plasma_path())
    print(client.store_capacity())
    print(client.list())
    client.delete(client.list())
    print(client.list())
    client.evict(10000000000)

    object_id = plasma.ObjectID(20 * b"a")
    object_size = 1000
    print(object_id)
    if client.contains(object_id):
        client.delete([object_id])

    buffer = memoryview(client.create(object_id, object_size))

    for i in range(1000):
        buffer[i] = i % 128
    client.seal(object_id)

    print("Generating...")
    data = np.ones(10**9)
    print("Done")
    tensor = pa.Tensor.from_numpy(data)

    random_id = plasma.ObjectID(np.random.bytes(20))
    sz = pa.ipc.get_tensor_size(tensor)
    print("sz", sz)
    buf = client.create(random_id, sz)

    stream = pa.FixedSizeBufferWriter(buf)
    stream.set_memcopy_threads(6)
    a = time.time()
    print("Writing...")
    pa.ipc.write_tensor(tensor, stream)
    print("Writing took ", time.time() - a)
    client.seal(random_id)

    #################################################################
    client2 = plasma.connect(get_plasma_path())

    t0 = time.time()
    print("Reading...")
    [buf2] = client.get_buffers([random_id])
    reader = pa.BufferReader(buf2)
    tensor2 = pa.ipc.read_tensor(reader)
    array = tensor2.to_numpy()
    # array[10] = 0
    # array2 = np.copy(array)
    # array2 = copy.deepcopy(array)
    # array2[10] = 0
    print("Reading took ", time.time() - t0)

    object_id2 = plasma.ObjectID(20 * b"a")
    [buffer2] = client2.get_buffers([object_id2], timeout_ms=1)
    view2 = memoryview(buffer2)
    for i in range(1000):
        if buffer[i] != view2[i]:
            print("Mismatch", i)

    meta = {"shape": (10, 20), "timestamps": [0, 1, 2], "other": 1.2}

    auto_id = client.put(meta)
    print(auto_id)
    got = client.get(auto_id, timeout_ms=1)
    print(got)
