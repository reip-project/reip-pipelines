import os
import struct
import json
import tqdm
import numpy as np
import reip
import matplotlib.pyplot as plt


def run(duration=4):
    srcs = {
        # 'Thread': lambda sink: sink.gen_source(),
        'Pickle': lambda sink: sink.gen_source(task_id=1111, throughput='small'),
        'Pyarrow': lambda sink: sink.gen_source(task_id=1111, throughput='medium'),
        'Plasma': lambda sink: sink.gen_source(task_id=1111, throughput='large'),
    }

    results = {}

    for name, get_src in srcs.items():
        sink = reip.Producer(task_id='asdf', size=100)
        src = get_src(sink)
        # print(name, src)

        sink.spawn()

        results[name] = {}
        for size in np.concatenate([np.arange(10, 100, 10), np.arange(100, 700, 50)]).astype(int):
            X = np.random.randn(size, size, size)
            gb = X.__sizeof__() / 8 / (1024**3)

            sw = reip.util.Stopwatch()
            i = 0

            try:
                for i, _ in tqdm.tqdm(
                        enumerate(reip.util.iters.timed(duration), 1),
                        leave=False, desc='{} {}'.format(name, X.shape)):
                    with sw(name):
                        sink.put((X, {}))
                        src.get()
                        src.next()
            except struct.error:  # too big for pickle
                import traceback
                traceback.print_exc()
                break
            except Exception as e:  # other exception?
                # results[name][gb] = np.nan
                import traceback
                traceback.print_exc()
                continue

            results[name][gb] = gb * i / sw.total(name)
            print('{}: {:.4f}gb/s.  Buffer Size: {:>16} {:.8f}gb.  Throughput: {:.4f}gb.  Runtime: {:.2f}s, {:>7} iterations'.format(
                name, results[name][gb], str(X.shape), gb, gb*i, sw.total(name), i))
        print()

        sink.join()

    for name, res in results.items():
        if name == 'thread':
            continue
        x, y = zip(*sorted(res.items()))
        plt.plot(x, y, label=name)

    plt.title('Throughput')
    plt.legend()
    plt.xlabel('Buffer Size (gb)')
    plt.ylabel('Throughput Speed (gb/s)')
    plt.xscale('log')
    plt.yscale('log')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'benchmarks-serialization.png'))

    with open(os.path.join(os.path.dirname(__file__), 'benchmarks-serialization.json'), 'w') as f:
        json.dump(results, f)



if __name__ == '__main__':
    import fire
    fire.Fire(run)
