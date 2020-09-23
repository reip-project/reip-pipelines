import time
import numpy as np
import matplotlib.pyplot as plt


class StopWatch:
    _avg_time = 0
    _avg_sleep = 0
    _avg_overhead = 0
    _calibrated = False

    def __init__(self, title="", max_samples=1e+6, calibrate=True, debug=False):
        self._max_samples = max_samples
        self._title = title
        self._samples = {}
        self._ticks = {}
        self._sums = {}
        # self._names = []
        # self._samples = []
        # self._ticks = []
        # self._sums = []

        if calibrate and not self._calibrated:
            self.calibrate(debug=debug)

    @classmethod
    def calibrate(cls, n=1000, debug=False, plot=False):
        cls._avg_time = 0
        cls._avg_sleep = 0
        cls._avg_overhead = 0
        cls._calibrated = False

        sw = StopWatch(title="StopWatch Calibration", calibrate=False, max_samples=10*n)

        measurements = []
        with sw():
            for i in range(n):
                t0 = time.time()
                with sw("test"):
                    t1 = time.time()
                    time.sleep(1e-6)
                    t2 = time.time()
                t3 = time.time()
                t4 = time.time()
                measurements.append((t0, t1, t2, t3, t4))

        us = 1e-6
        m = np.array(measurements) / us
        avg_time = np.average(m[:, 4] - m[:, 3])

        sleeps = m[:, 2] - m[:, 1] - avg_time
        ticks = m[:, 1] - m[:, 0] - avg_time
        tocks = m[:, 3] - m[:, 2] - avg_time

        avg_sleep, avg_tick, avg_tock = np.average(sleeps), np.average(ticks), np.average(tocks), 
        avg_overhead = sw["test"] / us - (avg_sleep + 2*avg_time)

        cls._avg_time = avg_time * us
        cls._avg_sleep = avg_sleep * us
        cls._avg_overhead = avg_overhead * us
        cls._calibrated = True

        if debug:
            print(sw)
            t = m[:, 4] - m[:, 3]
            print("Time resolution (us):", np.min(t[t > np.mean(t) / 5]))
            print("\navg_time:\t", avg_time, "\navg_tick:\t", avg_tick, "\navg_tock:\t", avg_tock,
                "\navg_sleep:\t", avg_sleep, "\navg_with:\t", avg_tick + avg_tock, "\navg_overhead:\t", avg_overhead, "\n")
            
        if plot:
            plt.figure("StopWatch Calibration (n=%d)" % n)

            plt.subplot(2, 3, 1, title="time")
            plt.hist(m[:, 4] - m[:, 3], bins=100, range=[0, 1])
            plt.xlabel("us")
            plt.subplot(2, 3, 2, title="tick")
            plt.hist(ticks, bins=100, range=[0, 25])
            plt.xlabel("us")
            plt.subplot(2, 3, 3, title="tock")
            plt.hist(tocks, bins=100, range=[0, 25])
            plt.xlabel("us")

            plt.subplot(2, 3, 4, title="sleep")
            plt.hist(sleeps, bins=100, range=[0, 100])
            plt.xlabel("us")
            plt.subplot(2, 3, 5, title="with = tick + tock")
            plt.hist(ticks + tocks, bins=100, range=[0, 50])
            plt.xlabel("us")
            plt.subplot(2, 3, 6, title="overhead")
            s = np.array(sw._samples["test"])
            # s = np.array(sw._samples[sw._names.index("test")])
            plt.hist((s[:, 1] - s[:, 0]) / us - (avg_sleep + 2*avg_time), bins=100, range=[0, 50])
            plt.xlabel("us")

            plt.tight_layout()  

    def reset(self):
        self._samples = {}
        self._ticks = {}
        self._sums = {}
        # self._names = []
        # self._samples = []
        # self._ticks = []
        # self._sums = []

    def tick(self, name=""):
        if name not in self._samples.keys():
            self._samples[name] = []
            self._sums[name] = 0
        self._ticks[name] = time.time()

        # if name not in self._names:
        #     self._names.append(name)
        #     self._samples.append([])
        #     self._sums.append(0)
        #     self._ticks.append(time.time())
        # else:
        #     self._ticks[self._names.index(name)] = time.time()

    def tock(self, name=""):
        # Correct for tick-tock overhead (~5 us on Jetson Nano - measured during calibration)
        t = (self._ticks[name], time.time() - self._avg_overhead)
        self._sums[name] += max(0, t[1] - t[0])
        s = self._samples[name]
        s.append(t)
        if len(s) > self._max_samples:
            self._samples[name] = s[len(s)//2:]

        # Correct for tick-tock overhead measured during calibration
        # i = self._names.index(name)
        # t = (self._ticks[i], time.time() - self._avg_overhead)
        # self._sums[i] += max(0, t[1] - t[0])
        # s = self._samples[i]
        # s.append(t)
        # if len(s) > self._max_samples:
        #     self._samples[i] = s[len(s)//2:]

    def __call__(self, name=""):
        return self.Lap(self, name)

    class Lap:
        def __init__(self, sw, name):
            self._sw = sw
            self._name = name

        def __enter__(self):
            self._sw.tick(self._name)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self._sw.tock(self._name)

    def stats(self, name=""):
        if name not in self._samples.keys():
            raise ValueError("Measurement unavailable for lap %s" % name)
        samples = np.array(self._samples[name])
        intervals = samples[:, 1] - samples[:, 0]
        total = self._sums[name]
        count = intervals.shape[0]
        return total, total/count, np.std(intervals), count

        # i = self._names.index(name)
        # # if name not in self._names:
        # #     raise ValueError("Measurement unavailable for lap %s" % name)
        # samples = np.array(self._samples[i])
        # intervals = samples[:, 1] - samples[:, 0]
        # total = self._sums[i]
        # count = intervals.shape[0]
        # return total, total/count, np.std(intervals), count

    def __getitem__(self, key):
        return self._sums[key] / len(self._samples[key])
        # i = self._names.index(key)
        # return self._sums[i] / len(self._samples[i])

    def __str__(self):
        total = None
        if "" in self._samples.keys():
            total = self._sums[""]
            s = "Total %.4f sec in %s:\n" % (total, self._title)

            if "service" not in self._samples.keys():
                added = np.sum([self._sums[k] for k, v in self._samples.items() if k != ""])
                self._samples["service"] = [(0, total - added)]
                self._sums["service"] = total - added
        else:
            s = ""

        s += "".join([("  %.4f" + ((" (%4.1f)" % (100. * self._sums[k] / total)) if total is not None else "") +
                      " - " + k + "  \t(avg = %.6f +- %.6f, n = %d)\n") %
                      self.stats(k) for k, v in self._samples.items() if k != ""])
        return s

        # total = None
        # if "" in self._names:
        #     total = self._sums[self._names.index("")]
        #     s = "Total %.4f sec in %s:\n" % (total, self._title)

        #     if "service" not in self._names:
        #         added = np.sum([self._sums[i] for i in range(len(self._names)) if self._names[i] != ""])
        #         self._names.append("service")
        #         self._samples.append([(0, total - added)])
        #         self._sums.append(total - added)
        # else:
        #     s = ""

        # s += "".join([("  %.4f" + ((" (%4.1f)" % (100. * self._sums[i] / total)) if total is not None else "") +
        #               " - " + self._names[i] + "  \t(avg = %.6f +- %.6f, n = %d)\n") %
        #               self.stats(self._names[i]) for i in range(len(self._names)) if self._names[i] != ""])
        # return s

    def plot(self):
        plt.figure(self._title, (16, 9))
        for i, (k, v) in enumerate(self._samples.items()):
            K = k if k != "" else "total"
            plt.subplot(2, (len(self._samples) + 1) // 2, i+1, title=K)
            samples = np.array(self._samples[k])
            intervals = samples[:, 1] - samples[:, 0]
            plt.hist(intervals, bins=100, label=K)
            plt.title((K + ": %.4f sec (avg = %.6f +- %.6f, n = %d)") % self.stats(k))
            plt.legend()
        plt.tight_layout()
        
        # plt.figure(self._title, (16, 9))
        # for i in range(len(self._names)):
        #     k = self._names[i]
        #     K = k if k != "" else "total"
        #     plt.subplot(2, (len(self._samples) + 1) // 2, i+1, title=K)
        #     samples = np.array(self._samples[i])
        #     intervals = samples[:, 1] - samples[:, 0]
        #     plt.hist(intervals, bins=100, label=K)
        #     plt.title((K + ": %.4f sec (avg = %.6f +- %.6f, n = %d)") % self.stats(k))
        #     plt.legend()
        # plt.tight_layout()


if __name__ == '__main__':
    sw = StopWatch(title="Test", debug=True)

    with sw():
        for repeat in range(10):
            for i in range(6):
                duration = 10**i
                with sw(str(duration)):
                    time.sleep(duration * 1.e-6)
    print(sw)
    sw.plot()

    StopWatch.calibrate(n=1000, plot=True)
    plt.show()
