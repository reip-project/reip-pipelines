import time
import numpy as np


class Stopwatch:
    class lap:
        def __init__(self, sw, name):
            self.sw = sw
            self.name = name

        def __enter__(self):
            self.sw.tick(self.name)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.sw.tock(self.name)

    def __init__(self, title='', max_samples=1e+6):
        self._max_samples = max_samples
        self._title = title
        self._dt = self._estimate_dt()[0]
        self.reset()

    def reset(self):
        self._samples = {}
        self._ticks = {}
        self._sums = {}
        self._counts = {}

    def _estimate_dt(self, n=100):
        dts = np.array([time.time() - time.time() for _ in range(n)])
        dt = np.min(dts[dts > np.mean(dts) / 2])
        return dt, dts

    def tick(self, name=''):
        if name not in self._samples:
            self._samples[name] = []
            self._sums[name] = 0
            self._counts[name] = 0
        self._ticks[name] = time.time()

    def tock(self, name=''):
        # Correct for time.time() execution time (dt) and Lap class overhead (approx 1 us)
        t = (self._ticks[name], time.time() - self._dt - 1e-6)
        self._sums[name] += max(0, t[1] - t[0])
        self._counts[name] += 1
        s = self._samples[name]
        s.append(t)
        if len(s) > self._max_samples:
            self._samples[name] = s[len(s)//2:]

    def last(self, name=''):
        ts = self._samples.get(name)
        return ts[-1][1] - ts[-1][0] if ts else None

    def sleep(self, delay=1e-6, name="sleep"):
        self.tick(name)
        time.sleep(delay)
        self.tock(name)

    def __call__(self, name=""):
        return self.lap(self, name)

    def stats(self, name=""):
        if name not in self._samples:
            raise ValueError(f'Measurement unavailable for lap {name!r}')
        samples = np.array(self._samples[name]).reshape(-1, 2) # reshape for len(0)
        intervals = samples[:, 1] - samples[:, 0]
        total = self._sums[name]
        count = self._counts.get(name, len(samples))
        return total, total/count if count else 0, np.std(intervals), count

    def __getitem__(self, key):
        return self._sums[key] / self._counts[key]

    def __str__(self):
        total = self._sums.get('')

        if total and 'service' not in self._samples:
            added = sum(self._sums[k] for k in self._samples if k)
            self._samples["service"] = [(0, total - added)]
            self._sums["service"] = total - added

        name_width = max((len(k) for k in self._samples), default=0) + 2
        stats = (
            (k, self.stats(k), 100 * self._sums[k] / total if total else 0)
            for k in self._samples if k)
        return (f'Total {total:.4f} sec in {self._title}:\n' if total else '') + (
            ''.join(
            f'    {0:.4f} ({percent:5.2f}%) - {name:<{name_width}} '
            f'(avg = {avg:.6f} ± {std:.6f}, n = {count:8,})\n'
            for (name, (total, avg, std, count), percent) in stats
        ) or '-- no stats available --')

    def plot(self, cols=2, figsize=(16, 9)):
        import matplotlib.pyplot as plt
        print(self)
        plt.figure(figsize=figsize)
        for i, k in enumerate(self._samples, 1):
            plt.subplot(cols, int(np.ceil(len(self._samples) / cols)), i)
            # plot distribution
            samples = np.array(self._samples[k])
            plt.hist(samples[:, 1] - samples[:, 0], bins=100)
            # set title with stats
            total, avg, std, count = self.stats(k)
            plt.title(
                f'{k or "total"}: {total} sec '
                f'(avg = {avg:.6f} ± {std:.6f}, n = {count:.0f})')
        plt.suptitle(self._title)
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    sw = Stopwatch("Test")

    dt, dts = sw._estimate_dt(100000)
    print("dt", dt)
    plt.figure("dt")
    plt.hist(dts, bins=200, range=[0, 1e-6])

    with sw():
        t0 = time.time()
        with sw("mini"):  # ~10 us overhead with ~1.5 us overestimate (corrected for)
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
