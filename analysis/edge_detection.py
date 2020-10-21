import os
import json
import librosa
import joblib
import numpy as np
import matplotlib.pyplot as plt
import scipy.io.wavfile as wav
from scipy.signal import find_peaks


def load_data(base_path, max_files=6, plot=True, save_plot=False, plot_channel=0):
    print("\nLoading:", base_path)
    data, filenames = [None] * max_files, [None] * max_files

    for i in range(max_files):
        filename = base_path % (i + 1)
        if not os.path.isfile(filename):
            continue
        print(filename)
        filenames[i] = filename
        data[i] = wav.read(filename, mmap=True)[1]

    if plot:
        plt.figure(base_path, (16, 9))
        stride, offset, lim = 1, 10000, 0
        for i in range(max_files):
            if data[i] is not None:
                plt.plot(data[i][::stride, plot_channel] - (i - (max_files-1) / 2) * offset, label="Sensor "+str(i+1))
                lim = max(lim, data[i].shape[0])
        plt.xlabel("Samples" + ("" if stride == 1 else " (with stride %d)" % stride))
        plt.ylabel("Amplitude (with %d offset)" % offset)
        plt.xlim([0, lim / stride])
        plt.legend(loc="upper right")
        plt.tight_layout()
        if save_plot:
            plt.savefig(base_path[:-7] + ".png", dpi=200)

    return data, filenames


def detect_edges(mono_data, title=None, w=512, plot=True, plot_all=False, save=True, verbose=True):
    # Compute spectrogram with stride w
    db = librosa.amplitude_to_db(np.abs(librosa.stft(mono_data.astype(np.float), hop_length=w)))
    db -= np.min(db)  # get rid of offset but typically does nothing because of overrun errors (min = 0)
    print("dB:", db.shape)

    spl = np.sum(db, axis=0)  # basic spl
    spl -= np.min(spl)  # get rid of possible offset just like for db
    spl /= np.max(spl)  # normalize to 1 for native threshold definition and plotting
    print("SPL:", spl.shape)

    thr, dist = 0.1, 48000 // w  # 10 %, 1 sec
    # print("Threshold:", thr, "Distance:", dist * w / 48000, "Window:", w)
    peaks, _ = find_peaks(spl, height=thr, distance=dist)
    print("%d peaks:" % len(peaks), peaks.tolist())

    title = title or "Mono"
    abs_data = np.abs(mono_data.astype(np.int))  # rectify for edge search
    x = np.arange(spl.shape[0]) * w  # prep scale for spl in audio samples
    s, edges = 2 * w, []  # real edge can be +- w off with respect to the approximate peak locations

    for i, p in enumerate(peaks):
        if plot_all and i % 25 == 0:
            plt.tight_layout()
            plt.figure("%s - Peaks %d+" % (title, i), (16, 9))

        ad = abs_data[x[p]-s:x[p]+s]  # window to search for the actual edge
        b = ad[w//4:3*w//4]  # a slice to establish baseline

        mean, std, m = np.mean(b), np.std(b), np.max(ad)  # some statistics
        # decide whether the peak is valid (has sharp edge) with some heuristics (rejects false overrun edges)
        good = True if (mean + 3 * std if np.max(b) > 0.5 else m) < m / 5 else False

        # compute the actual threshold for edge search (empirical)
        thr = min(m / 4, max(5 * np.max(b), m / 50) if np.max(b) > 0.5 else m / 10)
        idx = np.nonzero(ad[3*w//4:13*w//4] > thr)[0]

        if idx.shape[0] == 0:
            print("\n\tEmpty idx!\n")
            continue
        else:
            idx = np.min(idx)  # find edge
            pos = x[p] + idx - s + 3 * w // 4 + 1  # map to the absolute position

        if good:
            edges.append(pos)
        elif verbose:
            print("No edge found: peak %d at %d" % (i, p))

        # print("\t%.2f \t%.2f \t%.2f \t%.2f \t%.2f \t%.2f" % (mean, std, np.min(b), np.max(b), m, 100 * thr / m))

        if plot and plot_all:
            plt.subplot(5, 5, (i % 25) + 1, title=str(i))
            sl = abs_data[pos-200:pos+200]
            plt.plot(sl, "b" if good else "r")
            plt.plot([0, 401], [thr, thr], "k--")
            plt.plot([200, 200], [0, np.max(sl)], "k--")

    if plot:
        plt.tight_layout()
        plt.figure(title, (16, 9))
        plt.plot(abs_data, label="abs")
        plt.plot(0, 0)  # skip color
        sc = 0.25 * np.max(abs_data) / np.max(spl)
        plt.plot(x, spl * sc, label="db")
        plt.plot(x[peaks], spl[peaks] * sc, "x", label="peaks")
        plt.plot(edges, 0.25 * sc * np.ones((len(edges))), "r+", label="edges")
        plt.xlabel("Samples")
        plt.ylabel("Amplitude")
        plt.xlim([0, abs_data.shape[0]])
        plt.ylim([0, np.max(abs_data) / 3])
        plt.legend(loc="upper right")
        plt.tight_layout()

        if save:
            plt.savefig(title + ".png", dpi=200)

        if plot_all:
            plt.figure(title + " - Spectrogram", (16, 9))
            plt.imshow(db)
            plt.colorbar()
            plt.tight_layout()

    print("%d edges:" % len(edges), edges)
    edges = np.array(edges)

    if save:
        with open(title + ".json", "w") as f:
            json.dump({"edge_locations": edges.tolist()}, f)

    return edges


def detect_all_edges(data, filenames):
    for i in range(len(filenames)):
        if filenames[i] is None:
            continue

        jobs = [joblib.delayed(detect_edges, check_pickle=False)
                (data[i][:, ch], plot=False, save=False, verbose=False) for ch in range(12)]

        results = joblib.Parallel(verbose=15, n_jobs=-1, batch_size=1, pre_dispatch="all")(jobs)
        edges = [result.tolist() for result in results]

        with open(filenames[i][:-4] + ".json", "w") as f:
            json.dump({"edge_locations": edges}, f, indent=4)


if __name__ == '__main__':
    data_path = "/home/yurii/data"
    # filegroup = "/aligned/car_buzzer_and_hummer_grid_%d.wav"
    filegroup = "/aligned/sync_line_56_and_13_%d.wav"
    channel = 0

    data, filenames = load_data(data_path + filegroup, plot=True, save_plot=True, plot_channel=channel)

    # detect_edges(data[0][:, 0], plot=True, plot_all=True, save=False)

    detect_all_edges(data, filenames)

    # edges = [detect_edges(data[i][:, channel], plot=True, save=True, title=filenames[i][:-4]) for i in range(6)]
    # print(edges)

    plt.show()
