import os
import glob
import json
import numpy as np
import matplotlib.pyplot as plt
import scipy.io.wavfile as wav


def load_data(path):
    files = sorted(glob.glob(path + "/*.wav"))
    if not len(files):
        return None

    mapped = [wav.read(file, mmap=True)[1] for file in files]
    return np.concatenate(mapped, axis=0)  # makes a copy here?


def load_meta(path):
    filename = path + "/audio_timestamps.json"
    if not os.path.isfile(filename):
        return None

    with open(filename, "r") as f:
        meta = json.load(f)
        meta["timestamps"] = np.array(meta["timestamps"])
        return meta


def load_all(base_path):
    data, meta = [None] * 6, [None] * 6
    for i in range(6):
        path = base_path % (i + 1)
        data[i] = load_data(path)
        meta[i] = load_meta(path)
    return data, meta


def find_experiments(data_path):
    dirs = [x[0] for x in os.walk(data_path)]
    unique = set()
    for d in dirs:
        unique.add(os.path.basename(d))
    unique.discard("data")
    unique.discard("aligned")
    for i in range(6):
        unique.discard("reip_%d" % (i + 1))
    return unique


def align_data(experiments):
    for experiment in experiments:
        print("\nexperiment: %s" % experiment)
        data, meta = load_all(data_path + "/reip_%d/" + experiment)

        timestamps = [m["timestamps"] if m is not None else None for m in meta]
        min_t = max([t[0, 1] for t in timestamps if t is not None])
        max_t = min([t[-1, 1] for t in timestamps if t is not None])
        print("common range: %d %d (%d - %.3f sec @ 48 kHz)" %
              (min_t, max_t, max_t - min_t, (max_t - min_t) * 40 / 48000))

        if max_t < min_t:
            print("\tdiscarded")
            continue

        for i, (d, t) in enumerate(zip(data, timestamps)):
            if d is not None and t is not None:
                merged = np.zeros(((max_t - min_t + 10) * 40, 12), dtype=np.int16)
                print(i+1, merged.shape, "from", d.shape)
                for j in range(t.shape[0]):
                    ap, rt = t[j, :]
                    if rt < min_t or rt > max_t:
                        continue
                    new_ap = (rt - min_t) * 40
                    chunk = 400 if rt == max_t else 401
                    merged[new_ap:new_ap+chunk, :] = d[ap:ap+chunk, :12]

                wav.write(data_path + "/aligned/%s_%d.wav" % (experiment, i+1), 48000, merged)


def display_data(base_path, channel=0):
    print("\ndisplay:", base_path)
    data = [None] * 6
    for i in range(6):
        filename = base_path % (i + 1)
        if not os.path.isfile(filename):
            continue
        print(filename)
        data[i] = wav.read(filename, mmap=True)[1]

    plt.figure(base_path, (16, 9))
    for i, d in enumerate(data):
        if d is None:
            continue
        plt.plot(d[::10, channel] + (i+1) * 1000, label=str(i+1))
    plt.xlabel("Sample (every 10th)")
    plt.ylabel("Amplitude (with id*1000 offset)")
    plt.legend()
    plt.tight_layout()


if __name__ == '__main__':
    data_path = "/home/yurii/data"

    experiments = sorted(find_experiments(data_path))
    print("%d experiments in %s:" % (len(experiments), data_path), experiments)

    align_data(experiments)

    # display_data(data_path + "/aligned/sync_line_56_and_13_%d.wav")
    display_data(data_path + "/aligned/car_buzzer_and_hummer_grid_%d.wav")
    plt.show()
