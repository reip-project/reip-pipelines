import os
import glob
import time
import json
import joblib
import numpy as np
import matplotlib.pyplot as plt
import scipy.io.wavfile as wav


def load_data(path):
    mapped = [wav.read(file, mmap=True)[1] for file in sorted(glob.glob(path + "*.wav"))]
    data = np.concatenate(mapped, axis=0)  # makes a copy here

    with open(path + "all_timestamps.json", "r") as f:
        all = json.load(f)
        timestamps = np.stack([all["audio_position"], all["radio_timestamp"]], axis=1)

    with open(path + "reference_timestamps.json", "r") as f:
        reference = json.load(f)
        mb = reference["m"], reference["b"]
        # chuncks = np.stack([reference["audio_position"], reference["radio_timestamp"]], axis=1)


    data2 = np.zeros_like(data)

    a0 = all["audio_position"][0]
    t0 = all["radio_timestamp"][0]
    for i, (ap, rt) in enumerate(zip(all["audio_position"], all["radio_timestamp"])):
        if i == len(all["audio_position"]):
            break
        p = (rt - t0) * 40 + a0
        # l = all["audio_position"][i+1] - ap
        # if l != 400:
        #     print(i, p, ap, l)
        if p+400 > data2.shape[0]:
            break
        data2[p:p+400, :] = data[ap:ap+400, :]

    # ap = [all["audio_position"][0]]
    # rp = [all["radio_timestamp"][0]]
    # ap.extend(reference["audio_position"])
    # rp.extend(reference["radio_timestamp"])
    # ap.append(all["audio_position"][-1])
    # rp.append(all["radio_timestamp"][-1])
    # print(ap)
    # print(rp)

    # a0 = all["audio_position"][0]
    # t0 = all["radio_timestamp"][0]
    # chunks = [data[a0:reference["audio_position"][0], :]]
    #
    # # al, tl = a0, t0
    # tot = 0
    # for i, (ap, rt) in enumerate(zip(reference["audio_position"], reference["radio_timestamp"])):
    #     n = int(40 * (rt - (t0 + (ap-a0) / 40))) - tot
    #     print(i, ap, rt, n, n/40)
    #     tot += n
    #     # al, tl = ap, rt
    #     chunks.append(np.zeros((n, 16), dtype=np.int16))
    #     if i < len(reference["audio_position"])-1:
    #         chunks.append(data[ap:reference["audio_position"][i+1], :])
    #     else:
    #         chunks.append(data[ap:, :])

    # return data, timestamps, mb, np.concatenate(chunks, axis=0), t0
    return data2, timestamps, mb, data2, t0


if __name__ == '__main__':
    data_path = "/home/yurii/data/"
    base_path = data_path + "reip_%d/sync_line_56_and_13/"

    data, timestamps, mb, chunks, t0 = [None] * 6, [None] * 6, [None] * 6, [None] * 6, [None] * 6
    for i in range(6):
        print(i)
        data[i], timestamps[i], mb[i], chunks[i], t0[i] = load_data(base_path % (i + 1))
        mb[i] = 0.025, t0[i]
        # t0[i] = timestamps[i][0, 1]
    mb, t0 = np.array(mb), np.array(t0)
    # mb[:, 0] = np.average(mb[:, 0])
    mb[:, 0] = 0.025

    print(data, timestamps, mb)

    start_audio0 = 2000000
    start_radio = start_audio0 * mb[4, 0] + mb[4, 1]
    print("start_radio", start_radio)
    # start_audio = ((start_radio - mb[:, 1]) / mb[:, 0]).astype(np.int)
    start_audio = ((start_radio - t0) / mb[:, 0]).astype(np.int)
    print("start_audio", start_audio)

    l = 2000000
    samples = np.array([data[i][start_audio[i]:start_audio[i] + l, 0] for i in range(6)]).T
    # samples = np.array([data[i][start_audio0:start_audio0 + l, 0] for i in range(6)]).T
    print(samples)

    plt.figure("samples", (16, 9))
    for i in range(6):
        plt.plot(samples[::10, i] + i * 2000, label=str(i+1))
    plt.legend()
    plt.tight_layout()

    plt.show()
    exit(0)
