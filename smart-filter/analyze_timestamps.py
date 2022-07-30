import cv2
import glob
import json
import time

import logging
logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt
import numpy as np

import reip.util
import sys

import itertools
np.set_printoptions(threshold=sys.maxsize)
# from process_audio import *
# from process_videos import *
# from process_detections import *

from natsort import natsorted #For sorting string values considered as int

ms, us = 1.e-3, 1.e-6


#Process data for 1 sensor 
def preprocess(path,root):
    result = []
    index = ['0','1']
    for i in index:
        #Sorting filepaths and merging the files into one
        for file in natsorted(glob.glob(path + i +'*.json')):
            # print(file)
            with open(file,'rb') as infile:
                result.append(json.load(infile))    

        #Dumping merged file in root folder
        with open(root + i +"_merged.json", "w") as outfile:
            json.dump(result, outfile,indent=4)
        result = []


def sorting(root):
    #Open merged file for sorting
    index = ['0','1']
    for i in index:
        merged_list = []
        with open(root + i + "_merged.json",'rb') as infile:
            result= json.load(infile)    
        
        #Sort the dictionaries in merged file and append to list 
        
        for dictionary in result:
            for s in natsorted(dictionary.items()):
                if s[0].startswith('buffer'):
                    # merged_list.append({s[0]:s[1]})
                    merged_list.append(s[1])

        # Overwrite with merged file with list of tuples with dictionaries
        with open(root + i + "_merged.json",'w') as outfile:
            result = json.dump(merged_list,outfile,indent=4)    


def analyze_timestamps(ts, title, fps, n=10, bins=1000, debug=True, verbose=False, plot=True, savefigs=False):
    title, min_t = title.capitalize(), np.min(ts)
    ts = ts - min_t  # Work with relative values

    p_ref, dt = 1 / fps, np.diff(ts)
    # ps = dt[(0.99 * p_ref < dt) & (dt < 1.01 * p_ref)]
    # per = np.mean(ps)  # Inaccurate - use larger step

    p_ref_n, dt_n = n * p_ref, np.diff(ts[n::n])
    ps_n = dt_n[(0.95 * p_ref_n < dt_n) & (dt_n < 1.05 * p_ref_n)]
    per_n = np.mean(ps_n)  # Much better
    per = per_n / n

    # Compute median offset
    ofs = ts - np.round(ts/per) * per
    off = np.median(ofs)

    # Compute frame ids
    ids = np.round((ts - off) / per).astype(np.int)

    # Check for duplicates after rounding due to the frame acquisition delays
    for it in range(100):
        idx = np.nonzero(np.diff(ids) <= 0)[0]

        # Repeat until all consecutive delays are resolved (up to 100 iterations)
        if idx.shape[0] == 0:
            break

        for i in reversed(idx):
            ids[i] = ids[i+1] - 1

    # Remaining gaps (lost frames)
    gaps = np.nonzero(np.diff(ids) > 1)[0]
    lost = ids[gaps + 1] - ids[gaps] - 1

    if debug:
        print("\nAnalyzing %s timestamps ..." % title)
        print("fps:", fps)
        print("period:", per/ms, "ms")
        print("offset:", off/ms, "ms")

        if verbose:
            print("\tmin_t:", min_t, "sec")
            print("\trange:", [np.min(dt)/ms, np.max(dt)/ms], "ms")
            # print("ids:", (ts - off) / per)
            print("\tidx:", idx)

        print(len(gaps), "gaps:", ids[gaps] + 1)
        if len(lost):
            print(len(lost), "lost:", lost)

    if plot:
        plt.figure("Timeline - " + title, (16, 9))
        plt.plot(ids * per, ts, ".-", label="Received")
        plt.plot(ids * per, ids * per, "r-", label="Expected")
        plt.xlabel("Frame time, sec")
        plt.ylabel("Timestamp, sec")
        plt.title(title + " Timeline")
        plt.legend()
        plt.tight_layout()

        plt.figure("Periods Hist - " + title, (16, 9))
        plt.hist(ps_n/ms/n, bins=2*bins//n)
        plt.plot([per_n/ms/n, per_n/ms/n], [0, 100], "r-")
        # plt.semilogy()
        plt.xlabel("Period, ms")
        plt.ylabel("Counts")
        plt.title(title + " Periods" + " (avg = %.3f ms)" % (per_n/ms/n))
        plt.tight_layout()

        plt.figure("Periods All - " + title, (16, 9))
        plt.plot(dt/ms)
        plt.xlabel("Period #")
        plt.ylabel("Period, ms")
        plt.tight_layout()

        plt.figure("Delays - " + title, (16, 9))
        delays = (ts - ids * per) / ms
        plt.plot(ids, delays, "-", label="Delays")
        plt.plot(ids[[0, -1]], [off/ms, off/ms], "k--", label="Offset")

        for i, gap in enumerate(gaps):
            f0, t0, f1, t1 = ids[gap], delays[gap], ids[gap + 1], delays[gap + 1]
            dt = 0.5 * (t1 - t0) / (f1 - f0)
            plt.plot([f0 + 0.5, f1 - 0.5], [t0 + dt, t1 - dt], "m-", label="Gaps" if i == 0 else None)
            x = np.linspace(f0 + 1, f1 - 1, f1 - f0 - 1)
            y = np.linspace(t0 + 2 * dt, t1 - 2 * dt, f1 - f0 - 1)
            plt.plot(x, y, "r.", label="Lost" if i == 0 else None)

        plt.xlabel("Frame ID")
        plt.ylabel("Delay, ms")
        plt.title(title + " Delays")
        plt.legend()
        plt.tight_layout()

        # plt.figure("Offsets - " + title, (16, 9))
        # plt.hist(ofs/ms, bins=bins)
        # plt.plot([off/ms, off/ms], [0, 10], "r-")
        # plt.semilogy()
        # plt.xlabel("Offset, ms")
        # plt.ylabel("Counts")
        # plt.title(title + " Offsets")
        # plt.tight_layout()

        # plt.figure("Frame ID deltas - " + title, (16, 9))
        # plt.hist(np.diff(ids), bins=11, range=[-0.5, 10.5])
        # plt.semilogy()
        # plt.xlabel("Frame ID delta")
        # plt.ylabel("Counts")
        # plt.title(title + " Frame ID deltas")
        # plt.tight_layout()

        if savefigs:
            pass

    return ids, (gaps, lost), (per, off)


if __name__ == '__main__':
    path = "/home/reip/data/"

    preprocess(path + "time/", path)
    sorting(path)
    print("Done merging")

    # path = '/mnt/ssd/default_both/'
    cam_names, radio_freq = ["0", "1"], 1200
    # path = '/mnt/ssd/default_builtin/'
    # cam_names, radio_freq = ["builtin"], 1200

    # audio = json.load(open(path + "audio.json", "r"))
    # triggers = np.array(audio["triggers"])
    # triggers -= triggers[0, :]
    # trig_min, trig_max = np.min(triggers, axis=0), np.max(triggers, axis=0)
    # print(len(triggers), "triggers")

    # detections = json.load(open(path + "detections.json", "r"))
    # cam_names, radio_freq = detections["camera_names"], 1200
    # print("cam_names:", cam_names)
    #
    # det_ts = {}
    # for name in cam_names:
    #     det_ts[name] = np.array([[det["source_meta"][t] for t in ["python_timestamp", "global_timestamp"]]
    #                                                     for det in detections[name]])
    #
    # # Det range is always withing Cam range
    # det_min = np.array([min([np.min(det_ts[name][:, i]) for name in cam_names]) for i in range(2)])
    # det_max = np.array([max([np.max(det_ts[name][:, i]) for name in cam_names]) for i in range(2)])

    cam_ts = {}

    for name in cam_names:
        try:
            data = json.load(open(path + "%s_merged.json" % name, "r"))
        except:
            print("No read")
        # data = json.load(open(path + "", "r"))
        # t_names = ["python_timestamp", "global_timestamp",
        #             "basler_timestamp" if name == "basler" else "gstreamer_timestamp"]
        t_names = ["python_timestamp", "global_timestamp","gstreamer_timestamp"]
        # empty_list = []
        # for meta in data:
        #     for k,v in meta.items():
        #         empty_list.append([v[t_name] for t_name in t_names])
        
        # print(empty_list[:50])
        # print(np.array(empty_list))
        # cam_ts[name] = np.array(empty_list)
        cam_ts[name] = np.array([[meta[t_name] for t_name in t_names] for meta in data])
        # cam_ts[name] = np.array([[v[t_name] for t_name in t_names] for meta in data])

        # print(name, np.min(cam_ts[name][:, 1]), np.max(cam_ts[name][:, 1]))
        print(name, cam_ts[name].shape)

    cam_min = np.array([min([np.min(cam_ts[name][:, i]) for name in cam_names]) for i in range(2)])
    cam_max = np.array([max([np.max(cam_ts[name][:, i]) for name in cam_names]) for i in range(2)])

    # print(cam_min,cam_max)
    # print(cam_ts["builtin"][:, :2])

    # print("trig_range:", trig_min, "to", trig_max, " (", trig_max - trig_min, ")")
    # print("det_range:", det_min, "to", det_max, " (", det_max - det_min, ")")
    # print("cam_range:", cam_min, "to", cam_max, " (", cam_max - cam_min, ")")

    for name in cam_names:
        # print(cam_ts[name][:,:2], cam_ts[name][:,:2].shape)
        # print(cam_min, cam_min.shape)
        cam_ts[name][:, :2] -= cam_min
        cam_ts[name][:, 2] -= np.min(cam_ts[name][:, 2])  # Camera specific clock origin doesn't matter
        # det_ts[name] -= cam_min

        cam_ts[name][:, 1] /= radio_freq
        # det_ts[name][:, 1] /= radio_freq

    analyze_timestamps(cam_ts["0"][:, 2], "Camera_0", 14.4, verbose=True)
    analyze_timestamps(cam_ts["1"][:, 2], "Camera_1", 14.4, verbose=True)

    # analyze_timestamps(cam_ts["builtin1"][:, 2], "builtin_1", 3, verbose=True)



    plt.figure("Timeline", (16, 9))

    for name in cam_names:
        # cam, det = cam_ts[name] - cam_min, det_ts[name] - cam_min
        plt.plot(cam_ts[name][:, 1], cam_ts[name][:, 0], "+" if name == "0" else "x", label="Camera_"+name)
        # plt.plot(det_ts[name][:, 1], det_ts[name][:, 0], ".", label=name + "_det")

    plt.xlabel("Global time, sec")
    plt.ylabel("Python time, sec")
    plt.title("Timeline")
    plt.legend()
    plt.tight_layout()


    plt.figure("Intervals", (16, 9))

    for i, cam_name in enumerate(cam_names):
        t_names = ["python_timestamp", "global_timestamp",
                   "basler_timestamp" if cam_name == "basler" else "gstreamer_timestamp"]

        for j, t_name in zip(range(3), t_names):
            plt.subplot(len(cam_names), 3, i*3 + j + 1, title=cam_name + " - " + t_name)
            # plt.hist(np.diff(cam_ts[cam_name][:, j]), bins=150, range=[0, 0.015])
            # plt.hist(np.diff(cam_ts[cam_name][:, j]), bins=500, range=[0.0083, 0.0084])
            plt.hist(np.diff(cam_ts[cam_name][:, j]), bins=100)

    plt.tight_layout()


    plt.figure("Correlations", (16, 9))

    def correlate(x, y, ax=None, xlabel="x", ylabel="y"):
        mb = np.polyfit(x, y, 1)  # fit a line

        if ax is not None:
            ax.plot(x, y, ".", label="Data points")
            ax.plot(x, np.poly1d(mb)(x), "r-", label="Line fit")
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title("y=%f * x + %f" % (mb[0], mb[1]))
            ax.legend()

    for i, cam_name in enumerate(cam_names):
        t_names = ["python_timestamp", "global_timestamp",
                   "basler_timestamp" if cam_name == "basler" else "gstreamer_timestamp"]

        for j, (xi, yi) in enumerate([(2, 0), (0, 1)]):
            xl, yl = t_names[xi], t_names[yi]
            ax = plt.subplot(2, 2, i * 2 + j + 1, title="%s vs %s (%s)" % (yl, xl, cam_name))
            correlate(cam_ts[cam_name][:, xi], cam_ts[cam_name][:, yi], ax=ax, xlabel=xl, ylabel=yl)

    plt.tight_layout()

    plt.show()
