import time
import collections
import numpy as np
import reip
from reip.util.statistics import OnlineStats


_BLANK = ''

class Stopwatch:
    '''Stopwatch for timing and recording execution time of bits of code.
    
    .. code-block:: python

        sw = reip.util.Stopwatch()

        for _ in range(100):
            with sw('sleeping'):
                time.sleep(0.1)
    '''
    class lap:
        def __init__(self, sw, name=_BLANK):
            self.sw = sw
            self.name = name

        def __enter__(self):
            self.sw.tick(self.name)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.sw.tock(self.name)

    def __init__(self, title='', max_samples=500):
        self._max_samples = max_samples
        self._title = title
        self._dt = self._estimate_dt()[0]
        self.reset()

    # def __getstate__(self):
    #     return dict(self.__dict__, _samples={})

    def reset(self):
        # self._samples = {}
        self._ticks = {}
        self._stats = {}
        # self._sums = {}
        # self._counts = {}
        # self._stds = {}

    def __contains__(self, key):
        return key in self._stats

    def _estimate_dt(self, n=100):
        dts = []
        for i in range(n):
            t0 = time.time()
            t1 = time.time()
            dts.append(t1 - t0)
        dts = np.array(dts)
        dt = np.min(dts[dts > np.mean(dts) / 2])
        return dt, dts

    def tick(self, name=_BLANK):
        if name not in self._stats:
            self._stats[name] = OnlineStats(self._max_samples)
        self._ticks[name] = time.time()

    def tock(self, name=_BLANK, samples=True):
        # Correct for time.time() execution time (dt) and Lap class overhead (approx 1 us)
        t = (self._ticks[name], time.time() - self._dt - 1e-6)
        self._stats[name].append(max(0, t[1] - t[0]))
        # self._sums[name] += max(0, t[1] - t[0])
        # self._counts[name] += 1
        # if samples:
        #     s = self._samples[name]
        #     s.append(t)
        #     if len(s) > self._max_samples:
        #         self._samples[name] = s[len(s)//2:]

    def notock(self, name=_BLANK):
        self._ticks.pop(name, None)

    def ticktock(self, delta, name=_BLANK):
        self._stats[name].append(delta)
        # self._sums[name] += max(0, delta)
        # self._counts[name] += 1

    def iter(self, iterable, name=_BLANK, samples=True):
        self.tick(name)
        for item in iterable:
            self.tock(name, samples=samples)
            yield item
            self.tick(name)
        self.notock(name)

    def elapsed(self, name=_BLANK):
        if name in self._ticks.keys():
            return time.time() - self._ticks[name]
        else:
            print("Attention: No tick available right now for \"%s\"" % name)
            return 1e+6

    def last(self, name=_BLANK):
        ts = self._stats[name]
        return ts[-1][1] - ts[-1][0] if ts else None

    def avg(self, name=_BLANK):
        return self._stats[name].mean

    def total(self, name=_BLANK):
        return self._stats[name].sum

    def sleep(self, delay=1e-6, name="sleep"):
        self.tick(name)
        time.sleep(delay)
        self.tock(name, samples=False)

    def __call__(self, name=_BLANK):
        return self.lap(self, name)

    def __enter__(self):
        return self.lap(self).__enter__()

    def stats(self, name=_BLANK):
        if name not in self._stats:
            raise ValueError(f'Measurement unavailable for lap {name!r}')
        return self._stats[name]

    def __getitem__(self, key):
        return self.total(key)

    def __str__(self):
        total = self._stats[_BLANK].sum if _BLANK in self else 0

        if total and 'service' not in self._stats:
            added = sum(self._stats[k].sum for k in self._stats if k)
            service = self._stats['service'] = OnlineStats()
            service.append(total - added)

        name_width = max((len(k) for k in self._stats), default=0) + 2
        return ('Total {:.4f} sec in {}:\n'.format(total, self._title) if total else '') + (
            '\n'.join(
            ('    ({percent:5.2f}%) - {name:<{name_width}} '
             '(avg = {mean:.6f} ± {std:.6f}, n = {count:8,}) {total}').format(
                name=name, name_width=name_width,
                total=reip.util.human_time(stats.sum),
                percent=100. * stats.sum / total if total else 0,
                mean=stats.mean, std=stats.std, count=stats.count,
             )
            for name, stats in self._stats.items() if name
        ) or '-- no stats available --')

    def plot(self, cols=2, figsize=(16, 9)):
        import matplotlib.pyplot as plt
        print(self)
        plt.figure(figsize=figsize)
        for i, k in enumerate(self._stats, 1):
            plt.subplot(cols, int(np.ceil(len(self._stats[k].samples) / cols)), i)
            # plot distribution
            samples = np.array(self._stats[k].samples[k])
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
