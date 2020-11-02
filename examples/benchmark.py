import os
import struct
import json
import tqdm
import numpy as np
import reip
import matplotlib.pyplot as plt

plt.rc('font', family='serif')
plt.rc('axes', titlesize='x-large')
plt.rc('axes', labelsize='x-large')
plt.rc('legend', fontsize='large')
plt.rc('figure', titlesize='x-large')
plt.rc('xtick', labelsize='large')
plt.rc('ytick', labelsize='large')

DIR = os.path.join(os.path.dirname(__file__), 'benchmark_results')
RESULTS_FILE = os.path.join(DIR, '{}.json')
PLT_FILE = os.path.join(DIR, '{}.png')
DEFAULT_ID = 'serialization'

MARKERS = 'ovs*Xd+'
LINESTYLES = ['-', ':', '--', '-.']


def run(duration=3, id=DEFAULT_ID):
    os.makedirs(DIR, exist_ok=True)
    srcs = {
        # 'Thread': lambda sink: sink.gen_source(),
        'Pickle': lambda sink: sink.gen_source(task_id=1111, throughput='small'),
        'Pyarrow': lambda sink: sink.gen_source(task_id=1111, throughput='medium'),
        'Plasma': lambda sink: sink.gen_source(task_id=1111, throughput='large'),
    }

    results = {}

    for name, get_src in srcs.items():
        sink = reip.Producer(task_id='asdf', size=3)
        src = get_src(sink)
        # print(name, src)

        sink.spawn()

        results[name] = {}
        # for size in np.concatenate([np.arange(10, 100, 5), np.arange(100, 650, 50)]).astype(int):
        for size in np.logspace(2, 9, num=30, dtype=np.int):
            # sz = int(np.power(size, 1/3))
            # print(sz)
            X = np.ones(size, dtype=np.int8)
            mb = X.__sizeof__() / (1024**2)
            # print(X.dtype, X.__sizeof__(), gb)

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

            results[name][mb] = i / sw.total(name)
            print('{}: {:>9.3f} buffers/s.  Buffer Size: {:>15}+96 = {:>9.4f} mb.  Throughput: {:>9.3f} mb.  Runtime: {:.2f} sec,  {:>5} iterations'.format(
                name, results[name][mb], str(X.shape), mb, mb*i, sw.total(name), i))
        print()

        sink.join()

    _plot_results(results, id)
    with open(RESULTS_FILE.format(id), 'w') as f:
        json.dump(results, f, indent=4)


# def _plot_results(results, id=DEFAULT_ID):
#     plt.figure(figsize=(8, 6), dpi=300)
#     for (name, res), marker, ls in zip(results.items(), MARKERS, LINESTYLES):
#         x, y = zip(*sorted(((float(k), float(v)) for k, v in res.items())))
#         plt.plot(x, y, label=name, color='k', ls=ls)  # , marker=marker, markersize=4
#
#     plt.legend()
#     plt.xlabel('Buffer Size (gb)')
#     plt.ylabel('Speed (buffers/sec)')
#     plt.xscale('log')
#     plt.yscale('log')
#     plt.title('Buffer throughput speeds vs serialization.')
#     plt.tight_layout()
#     plt.savefig(PLT_FILE.format(id))


def _plot_lines(results, mbps=False):
    for (name, res), marker, ls in zip(results.items(), MARKERS, LINESTYLES):
        x, y = zip(*sorted(((float(k), float(v)) for k, v in res.items() if float(k) > 0.9e-3)))
        if mbps:
            y = [x*y for x, y in zip(x, y)]
        plt.plot(x, y, label=name, color='k', ls=ls)  # , marker=marker, markersize=4


def _plot_results(results, id=DEFAULT_ID):
    plt.figure(figsize=(8, 6))

    ax = plt.subplot(2, 1, 1, title="Buffer Throughput")
    _plot_lines(results, mbps=False)
    plt.legend()
    plt.gca().xaxis.set_visible(False)
    plt.ylabel('Speed, buffers/sec')
    plt.xscale('log')
    plt.xlim([1e-3, 1e+3])
    # plt.xticks([1000**i for i in np.linspace(-2, 0, 9)], ['{}{}'.format(i, u) for u in ['kb', 'mb', 'gb'] for i in [1, 10, 100]])
    plt.yscale('log')

    plt.subplot(2, 1, 2, sharex=ax, title="Data Throughput")
    _plot_lines(results, mbps=True)
    plt.xlabel('Buffer Size, MB')
    plt.ylabel('Speed, MB/sec')
    plt.xscale('log')
    # plt.xticks([1000**i for i in np.linspace(-2, 0, 9)], ['{}{}'.format(i, u) for u in ['kb', 'mb', 'gb'] for i in [1, 10, 100]])
    plt.yscale('log')
    # plt.suptitle('Buffer throughput speeds vs serialization.')

    plt.tight_layout()
    plt.savefig(PLT_FILE.format(id), dpi=300)


def plot(id=DEFAULT_ID, **kw):
    with open(RESULTS_FILE.format(id), 'r') as f:
        results = json.load(f)
    _plot_results(results, id, **kw)


if __name__ == '__main__':
    # plot()
    # plt.show()
    # exit()

    import fire
    fire.Fire()
