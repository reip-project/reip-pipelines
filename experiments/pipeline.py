import time
import queue
from interface import Source
from ring_buffer import RingBuffer
from dummies import Generator, Transformer, Consumer

if __name__ == '__main__':
    gen = Generator("data_gen", (720, 1280, 3), sink=RingBuffer(1000))
    trans = Transformer("data_trans", 10, sink=RingBuffer(1000))
    eat = Consumer("data_eat", "test", sink=queue.Queue())

    gen.child(trans, strategy=Source.Latest)
    # gen.child(trans, strategy=Source.Skip, skip=1)
    trans.child(eat, strategy=Source.All)

    eat.spawn()
    trans.spawn()
    gen.spawn()
    # while not gen.ready:
    #     time.sleep(1e-3)

    eat.start()
    trans.start()
    gen.start()
    time.sleep(0.1)

    # gen.terminate = True
    gen.join()
    trans.join()
    eat.join()

    gen.print_stats()
    trans.print_stats()
    eat.print_stats()

    print("Generated", gen._processed, "buffers")
    print("Transformed", trans._processed, "buffers")
    print("Consumed", eat._processed, "buffers")

    files = []
    while not eat.sink.empty():
        files.append(eat.sink.get())
    print(len(files), "files")
