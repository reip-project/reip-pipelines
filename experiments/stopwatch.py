import time
import numpy as np
import matplotlib.pyplot as plt


class StopWatch:
    def __init__(self, title="", max_samples=1000):
        self._max_samples = max_samples
        self._title = title
        self._samples = {}
        self._ticks = {}

    def tick(self, name=""):
        self._ticks[name] = time.time()

    def tock(self, name=""):
        t = time.time()
        if name not in self._samples.keys():
            self._samples[name] = []
        self._samples[name].append((self._ticks[name], t))
        l = len(self._samples[name])
        if l > self._max_samples:
            self._samples[name] = self._samples[name][l//2:]

    def _stats(self, name=""):
        if name not in self._samples.keys():
            return None, None, None, None
        samples = np.array(self._samples[name])
        intervals = samples[:, 1] - samples[:, 0]
        total = np.sum(intervals)
        count = intervals.shape[0]
        return total, count, total/count, np.std(intervals),

    def __str__(self):
        s = ""

        if "" in self._samples.keys():
            total = self._stats()[0]
            s += "Total %.3f sec:\n" % total

            if "service" not in self._samples.keys():
                added = np.sum([self._stats(k)[0] for k, v in self._samples.items() if k != ""])
                self._samples["service"] = [(0, total - added)]

        s += "".join([("\t%.6f - "+k+" \t(n=%d, mean=%.6f, std=%.6f)\n") % self._stats(k)
                     for k, v in self._samples.items() if k != ""])
        return s

    def plot(self):
        print(self)
        plt.figure(self._title, (16, 9))
        for i, (k, v) in enumerate(self._samples.items()):
            K = k if k != "" else "total"
            plt.subplot(2, (len(self._samples) + 1) // 2, i+1, title=K)
            samples = np.array(self._samples[k])
            intervals = samples[:, 1] - samples[:, 0]
            plt.hist(intervals, bins=100, label=K)
            plt.title((K+": %.6f sec [n=%d] mean=%.6f, std=%.6f") % self._stats(k))
            plt.legend()
        plt.tight_layout()


if __name__ == '__main__':
    sw = StopWatch("Test")

    sw.tick()

    t0 = time.time()
    sw.tick("mini")
    t1 = time.time()
    time.sleep(1e-6)
    t2 = time.time()
    sw.tock("mini")
    t3 = time.time()
    dt = time.time() - t3

    print("total", time.time() - t0 - 3*dt)
    print("tick", t1 - t0)
    print("sleep", t2 - t1)
    print("tock", t3 - t2)
    print("dt", dt)
    print("")

    sw.tick("init")
    time.sleep(0.1)
    sw.tock("init")

    for i in range(10):
        sw.tick("process")
        time.sleep(0.01)
        sw.tock("process")

    sw.tick("finish")
    time.sleep(0.1)
    sw.tock("finish")

    sw.tock()

    # print(sw)
    # print(sw)
    sw.plot()
    plt.show()
