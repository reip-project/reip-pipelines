import os
import struct
import json
import tqdm
import numpy as np
import reip
import matplotlib.pyplot as plt

plt.rc('font', family='serif')
plt.rc('xtick', labelsize='x-small')
plt.rc('ytick', labelsize='x-small')

DIR = os.path.join(os.path.dirname(__file__), 'benchmark_results')
RESULTS_FILE = os.path.join(DIR, '{}.json')
PLT_FILE = os.path.join(DIR, '{}.png')
DEFAULT_ID = 'serialization'

MARKERS = 'ovs*Xd+'
LINESTYLES = ['-', ':', '--', '-.']

def run(duration=6, id=DEFAULT_ID):
    os.makedirs(DIR, exist_ok=True)
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
        for size in np.concatenate([np.arange(10, 100, 5), np.arange(100, 700, 50)]).astype(int):
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

            results[name][gb] = i / sw.total(name)
            print('{}: {:.4f}gb/s.  Buffer Size: {:>16} {:.8f}gb.  Throughput: {:.4f}gb.  Runtime: {:.2f}s, {:>7} iterations'.format(
                name, results[name][gb], str(X.shape), gb, gb*i, sw.total(name), i))
        print()

        sink.join()

    _plot_results(results, id)
    with open(RESULTS_FILE.format(id), 'w') as f:
        json.dump(results, f)



def _plot_results(results, id=DEFAULT_ID):
    plt.figure(figsize=(7, 3), dpi=300)
    for (name, res), marker, ls in zip(results.items(), MARKERS, LINESTYLES):
        x, y = zip(*sorted(((float(k), float(v)) for k, v in res.items())))
        plt.plot(x, y, label=name, color='k', ls=ls)  # , marker=marker, markersize=4

    plt.legend()
    plt.xlabel('Buffer Size (gb)')
    plt.ylabel('Speed (buffers/sec)')
    plt.xscale('log')
    plt.yscale('log')
    plt.title('Buffer throughput speeds across several serialization strategies.')
    plt.tight_layout()
    plt.savefig(PLT_FILE.format(id))

def plot(id=DEFAULT_ID):
    with open(RESULTS_FILE.format(id), 'r') as f:
        results = json.load(f)
    _plot_results(results, id)

if __name__ == '__main__':
    import fire
    fire.Fire()
