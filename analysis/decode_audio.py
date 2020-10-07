import os
import glob
import time
import json
import joblib
import numpy as np
import matplotlib.pyplot as plt
import scipy.io.wavfile as wav


def extract_single(path, silent=False, plot=False, save=True):
    files = sorted(glob.glob(path + "/*.wav"))
    print("%d files in %s:" % (len(files), path), files)
    if len(files) == 0:
        return

    mapped = [wav.read(file, mmap=True)[1] for file in files]
    data = np.concatenate(mapped, axis=0)  # makes a copy here
    print("data:", data.shape)

    sync = data[:, -1]  # last channel contains the timestamps
    b = sync < 0  # digitize the signal
    es = np.diff(b)  # find edges
    ei = np.nonzero(es)[0]  # find edges location
    l = np.diff(ei)  # find distance between consecutive edges
    # timestamps starts after a constant for more than 200 audio samples
    e0 = ei[np.nonzero(l > 200)[0] + 1] + 5  # +1 moves to start bit and +5 skips it (5 audio samples per bit)
    e0 = e0[:-1]  # last timestamp might be incomplete
    n = e0.shape[0]  # total timestamps to decode
    off = np.tile(np.arange(32), (n, 1)) * 5 + 3  # offsets to sample 32-bits for each timestamp
    off = off + e0[:, None]  # move to zero bit positions
    bits = b[off.ravel()].reshape((n, 32)).astype(np.uint8)  # sample timestamp bits in the middle of 5 audio samples
    t = np.packbits(bits, axis=-1, bitorder="little")  # pack bits into bytes first
    ts = np.sum(t * np.array([1, 2 ** 8, 2 ** 16, 2 ** 24])[None, :], axis=1)  # now pack bytes into timestamps
    err = np.nonzero(np.diff(ts) - 10)[0]  # detect decoding errors (due to the firmware bug)

    if not silent:
        print("audio:", e0)
        print("radio:", ts)
        print(len(err), "errors:", err)
        for i in range(err.shape[0]):
            r0, r1 = 0 if i == 0 else err[i - 1], err[i]
            t0, t1 = ts[err[i]], ts[err[i] + 1]
            print("%3d %9d %15d %15d %15d %15d %.4f" % (i, r1, t0, t1, t1 - t0, r1 - r0, (t1 - t0) / (r1 - r0)))

    e0, ts = np.delete(e0, err), np.delete(ts, err)  # delete bad timestamps

    if save:
        with open(path + "/all_timestamps.json", "w") as f:
            json.dump({"audio_position": e0.tolist(), "radio_timestamp": ts.tolist()}, f, indent=4)

    step = np.nonzero(np.diff(ts) - 10)[0]  # detect timestamp discontinuities
    if len(step) < 2:
        print("Not enough discontinuities:", len(step))
        return

    x, y = e0[step+1], ts[step+1]
    # x, y = e0[::100], ts[::100]
    m, b = np.polyfit(x, y, 1)  # fit a line

    if not silent:
        print(len(step), "discontinuities:", step)
    print(m, b)

    with open(path + "/reference_timestamps.json", "w") as f:
        json.dump({"audio_position": x.tolist(), "radio_timestamp": y.tolist(),
                   "m": m, "b": b, "help": "radio_timestamp = audio_position * m + b"}, f, indent=4)
    if plot:
        plt.figure(path, (16, 9))
        plt.plot(x, y, "b.")
        plt.plot(x, x * m + b, "r-")
        plt.tight_layout()


def extract_all(data_path):
    dirs = [x[0] for x in os.walk(data_path)]
    print(len(dirs), "dirs in %s:" % data_path, dirs)

    for d in dirs:
        extract_single(d, silent=True, plot=False)


if __name__ == '__main__':
    data_path = "/home/yurii/data/"

    extract_single(data_path + "reip_6/sync_line_56_and_13", silent=False, plot=True, save=False)

    # for i in range(6):
    #     extract_all(data_path + "reip_%d/" % (i + 1))

    plt.show()
    exit(0)

    # data_path = "/home/yurii/data/reip_1/calib_test"
    # data_path = "/home/yurii/data/reip_1/test"
    # data_path = "/home/yurii/data/reip_1/line_test"
    # data_path = "/home/yurii/data/reip_1/car_buzzer_and_hummer_grid"
    # os.chdir(data_path)
    #
    # files = sorted(glob.glob("*.wav"))
    # print(data_path)
    # print(files)
    #
    # all_data = []
    # for i, file in enumerate(files):
    #     rate, data = wav.read(file, mmap=True)
    #     print(i, file, rate, data.shape)
    #     all_data.append(data)
    #
    # all_data = np.concatenate(all_data, axis=0)
    # print(all_data.shape)
    # print(all_data)
    #
    # sync = all_data[:, 15]
    # b = sync < 0
    # print(b)
    # e = np.diff(b)
    # print(e)
    # ei = np.nonzero(e)[0]
    # print(ei)
    # l = np.diff(ei)
    # print(l)
    # # +1 moves to start bit and +5 skips the start bit
    # e0 = ei[np.nonzero(l > 200)[0] + 1] + 5
    # print(e0)
    # # last timestamp might be incomplete
    # e0 = e0[:-1]
    # print(e0)
    # n = e0.shape[0]
    # print(n)
    # off = np.tile(np.arange(32), (n, 1)) * 5 + 3
    # print(off)
    # off = off + e0[:, None]
    # bits = b[off.ravel()].reshape((n, 32)).astype(np.uint8)
    # print(bits)
    # # pack bits into bytes first
    # t = np.packbits(bits, axis=-1, bitorder="little")
    # print(t)
    # # pack bytes into timestamps
    # timestamps = np.sum(t * np.array([1, 2**8, 2**16, 2**24])[None, :], axis=1)
    # print(timestamps)
    #
    # err = np.nonzero(np.diff(timestamps) - 10)[0]
    # for i in range(err.shape[0]):
    #     print("%3d %9d %15d %15d %15d %15d" % (i, err[i], timestamps[err[i] - 1], timestamps[err[i]], timestamps[err[i] + 1], timestamps[err[i] + 1] - timestamps[err[i]]))
    #
    # plt.figure("sync", (16, 9))
    # # plt.plot(all_data[:rate, 12:])
    # plt.plot(sync[:rate//20], ".-")
    # plt.plot(b[:rate//20] * 2**15)
    # plt.plot(e[:rate//20] * 2**15, "r.")
    # plt.plot(ei[:rate//1000], np.ones((rate//1000)) * 2**15, "g.")
    # plt.plot(e0[:10], np.ones((10)) * 2**15, "b.")
    # plt.tight_layout()
    #
    # plt.figure("dist", (16, 9))
    # plt.hist(l, bins=1000)
    # plt.tight_layout()
    #
    # plt.figure("time", (16, 9))
    # plt.hist(np.diff(timestamps), bins=1000)
    # plt.tight_layout()
    #
    # plt.figure("durr", (16, 9))
    # plt.hist(np.diff(e0), bins=1000)
    # plt.tight_layout()
    #
    # i = 0
    # plt.figure("err", (16, 9))
    # plt.plot(sync[err[i]*400-2000:err[i]*400+2000])
    # plt.tight_layout()
    #
    # e0 = np.delete(e0, err)
    # timestamps = np.delete(timestamps, err)
    # # timestamps = timestamps - timestamps[0]
    # print(e0.shape, e0)
    # print(timestamps.shape, timestamps)
    #
    # err2 = np.nonzero(np.diff(timestamps) - 10)[0]
    # print(err2)
    # for i in range(err2.shape[0]):
    #     r0, r1 = 0 if i == 0 else err2[i-1], err2[i]
    #     t0, t1 = timestamps[err2[i]], timestamps[err2[i] + 1]
    #     print("%3d %9d %15d %15d %6d %6d %.4f" % (i, r1, t0, t1, t1 - t0, r1-r0, (t1 - t0)/(r1-r0)))
    #
    # plt.figure("timestamps", (16, 9))
    # plt.plot(e0, timestamps - timestamps[0], "b-")
    # dt = timestamps[-1] - timestamps[0]
    # print(timestamps[0], timestamps[-1], dt)
    # plt.plot(err * 400, np.ones_like(err) * dt / 2, "r.")
    # plt.plot(err2 * 400, np.ones_like(err2) * dt / 2.2, "g.")
    # plt.tight_layout()
    #
    # plt.show()
