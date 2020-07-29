import time
import numpy as np
import matplotlib.pyplot as plt


class StopWatch:
    class Lap:
        def __init__(self, sw, name):
            self._sw = sw
            self._name = name

        def __enter__(self):
            self._sw.tick(self._name)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self._sw.tock(self._name)

    def __init__(self, title="", max_samples=1000):
        self._max_samples = max_samples
        self._title = title
        self._samples = {}
        self._ticks = {}
        self._dt = self._estimate_dt()[0]

    def _estimate_dt(self, n=100):
        dts = []
        for i in range(n):
            t0 = time.time()
            t1 = time.time()
            dts.append(t1 - t0)
        dts = np.array(dts)
        dt = np.min(dts[dts > np.mean(dts) / 2])
        return dt, dts

    def tick(self, name=""):
        if name not in self._samples.keys():
            self._samples[name] = []
        self._ticks[name] = time.time()

    def tock(self, name=""):
        t = time.time()
        l = self._samples[name]
        # Correct for time.time() execution time (dt) and Lap class overhead (approx 1 us)
        l.append((self._ticks[name], t - self._dt - 1e-6))
        if len(l) > self._max_samples:
            self._samples[name] = l[len(l)//2:]

    def __call__(self, name=""):
        return self.Lap(self, name)

    def _stats(self, name=""):
        if name not in self._samples.keys():
            raise ValueError("Measurement unavailable for lap %s" % name)
        samples = np.array(self._samples[name])
        intervals = samples[:, 1] - samples[:, 0]
        total = max(0, np.sum(intervals))
        count = intervals.shape[0]
        return total, total/count, np.std(intervals), count

    def __getitem__(self, key):
        return self._stats(key)[1]

    def __str__(self):
        total = None
        if "" in self._samples.keys():
            total = self._stats()[0]
            s = "Total %.4f sec in %s:\n" % (total, self._title)

            if "service" not in self._samples.keys():
                added = np.sum([self._stats(k)[0] for k, v in self._samples.items() if k != ""])
                self._samples["service"] = [(0, total - added)]
        else:
            s = ""

        s += "".join([("  %.4f" + ((" (%4.1f)" % (100. * self._stats(k)[0] / total)) if total is not None else "") +
                      " - " + k + "  \t(avg = %.6f +- %.6f, n = %d)\n") %
                      self._stats(k) for k, v in self._samples.items() if k != ""])
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
            plt.title((K + ": %.4f sec (avg = %.6f +- %.6f, n = %d)") % self._stats(k))
            plt.legend()
        plt.tight_layout()


if __name__ == '__main__':
    sw = StopWatch("Test")

    dt, dts = sw._estimate_dt(100000)
    print("dt", dt)
    plt.figure("dt")
    plt.hist(dts, bins=200, range=[0, 1e-6])

    with sw():
        t0 = time.time()
        with sw("mini"):  # ~6 us overhead with ~1.5 us overestimate (corrected for)
            t1 = time.time()
            time.sleep(1e-6)
            t2 = time.time()
        t3 = time.time()

        tick = t1 - t0
        sleep = t2 - t1
        tock = t3 - t2
        total = t3 - t0
        print("tick", tick)
        print("sleep", sleep)
        print("tock", tock)
        print("total", total)
        print("service", tick + tock - 2*dt)
        print("job", sleep + dt)
        print("")

        with sw("init"):
            time.sleep(0.1)

        for i in range(10):
            with sw("process"):
                time.sleep(0.01)

        with sw("finish"):
            time.sleep(0.1)

    sw.plot()
    plt.show()
