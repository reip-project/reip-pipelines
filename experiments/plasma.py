import pyarrow as pa
import numpy as np
import pyarrow.plasma as plasma
import time
import copy


def random_object_id():
    return plasma.ObjectID(np.random.bytes(20))


def save_data(client, data, id=None):
    t0 = time.time()
    print("Saving data...")
    if data is None:
        meta = "void"
        object_size = 0
    elif type(data) is str:
        meta = "string"
        object_size = len(data)
    elif type(data) is np.ndarray:
        meta = "array"
        tensor = pa.Tensor.from_numpy(data)
        object_size = pa.ipc.get_tensor_size(tensor)
    else:
        raise ValueError("Unsupported data type")

    object_id = id or plasma.ObjectID(np.random.bytes(20))

    if client.contains(object_id):
        client.delete([object_id])

    if data is None or type(data) is str:
        client.create_and_seal(object_id, (data or "").encode("utf-8"), metadata=meta.encode("utf-8"))
    else:
        buf = client.create(object_id, object_size, metadata=meta.encode("utf-8"))
        stream = pa.FixedSizeBufferWriter(buf)
        stream.set_memcopy_threads(6)
        pa.ipc.write_tensor(tensor, stream)
        client.seal(object_id)

    print("Saving data took", time.time() - t0)
    return object_id


def load_data(client, id):
    t0 = time.time()
    print("Loading data...")
    if not client.contains(id):
        raise ValueError("Object doesn't exist: %s" % id)

    meta = client.get_metadata([id], timeout_ms=1)[0].to_pybytes().decode("utf-8")

    if meta == "void":
        data = None
    elif meta == "string":
        data = client.get_buffers([id], timeout_ms=1)[0].to_pybytes().decode("utf-8")
    elif meta == "array":
        [buf] = client.get_buffers([id])
        reader = pa.BufferReader(buf)
        tensor = pa.ipc.read_tensor(reader)
        data = tensor.to_numpy()
    else:
        raise ValueError("Unsupported data type")

    print("Loading data took", time.time() - t0)
    return data


def save_meta(client, meta, id=None):
    t0 = time.time()
    print("Saving meta...")
    if type(meta) is dict:
        object_id = client.put(meta, object_id=id or plasma.ObjectID(np.random.bytes(20)))
    else:
        raise ValueError("Unsupported meta type")

    print("Saving meta took", time.time() - t0)
    return object_id


def load_meta(client, id):
    t0 = time.time()
    print("Loading meta...")
    if not client.contains(id):
        raise ValueError("Object doesn't exist: %s" % id)

    meta = client.get([id], timeout_ms=1)[0]

    print("Loading meta took", time.time() - t0)
    return meta


def save_both(client, data, meta, id=None, debug=False):
    if debug:
        t0 = time.time()
        print("Saving data with meta...")

    if data is None:
        meta["type"] = "void"
        object_size = 0
    elif type(data) is str:
        meta["type"] = "string"
        data = data.encode("utf-8")
        object_size = len(data)
    elif type(data) is np.ndarray:
        meta["type"] = "array"
        tensor = pa.Tensor.from_numpy(data)
        object_size = pa.ipc.get_tensor_size(tensor)
    else:
        raise ValueError("Unsupported data type")

    # print(object_size)
    if type(meta) is dict:
        meta = pa.serialize(meta).to_buffer().to_pybytes()
    else:
        raise ValueError("Unsupported meta type")

    object_id = id or plasma.ObjectID(np.random.bytes(20))

    buf = client.create(object_id, object_size, metadata=meta)
    stream = pa.FixedSizeBufferWriter(buf)
    if type(data) is bytes:
        stream.write(data)
    elif data is not None:
        stream.set_memcopy_threads(4)
        pa.ipc.write_tensor(tensor, stream)
    client.seal(object_id)

    if debug:
        print("Saving data with meta took", time.time() - t0)
    return object_id


def load_both(client, id, debug=False):
    if debug:
        t0 = time.time()
        print("Loading data with meta...")

    meta, data = client.get_buffers([id], timeout_ms=1, with_meta=True)[0] #.to_pybytes().decode("utf-8")
    meta = pa.deserialize(meta)
    if type(meta) != dict:
        raise ValueError("Unsupported meta type")

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

    if debug:
        print("Loading data with meta took", time.time() - t0)
    return data, meta


def test():
    client = plasma.connect("/tmp/plasma")
    print(client.store_capacity())
    print(client.list())
    client.delete(client.list())
    print(client.list())

    print("Generating...")
    data = np.ones(1 * 10 ** 7, dtype=np.uint8)
    # data = "Hello"
    # data = None
    print("Done")

    id = save_data(client, data)
    data2 = load_data(client, id)
    print(data2)
    client.delete([id])

    meta = {"Foo": 10}

    id2 = save_meta(client, meta)
    meta2 = load_meta(client, id2)
    print(meta2)

    # ~1 GB/s for image-sized buffers on Jetson Nano (~8 ms per 5 MP image in I420 format)
    id3 = save_both(client, data, meta, debug=True)
    # ~1.5 ms on Jetson Nano
    data3, meta3 = load_both(client, id3, debug=True)
    print(data3, meta3)


if __name__ == '__main__':
    test()
    exit(0)

    client = plasma.connect("/tmp/plasma")
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
    client2 = plasma.connect("/tmp/plasma")

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
