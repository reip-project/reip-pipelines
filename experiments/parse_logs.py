import json
import numpy as np
import matplotlib.pyplot as plt

def to_seconds(s):
    hr, min, sec = [float(x) for x in s.split(':')]
    return hr*3600 + min*60 + sec

def extract(gst_log, script_log, debug=False):
    with open(gst_log, "r") as f:
        lines = f.readlines()

    id_s = "create:<v4l2src"
    st_s = "sync to "
    ts_s = "out ts "
    lf_s = "lost frames detected: count = "

    st_l, ts_l, lf_l = [[], []], [[], []], [[], []]

    for line in lines:
        id_p = line.find(id_s)
        st_p = line.find(st_s)
        ts_p = line.find(ts_s)
        lf_p = line.find(lf_s)
        if id_p > 0:
            id_p += len(id_s)
            id = int(line[id_p:id_p+1])
        if st_p > 0 and ts_p > 0:
            st_p += len(st_s)
            ts_p += len(ts_s)
            st = to_seconds(line[st_p:st_p+17])
            ts = to_seconds(line[ts_p:ts_p+17])
            if debug:
                print(id, st, ts)
            st_l[id].append(st)
            ts_l[id].append(ts)
        if lf_p > 0:
            lf_p += len(lf_s)
            line = line[lf_p:]
            lf = int(line.split()[0])
            p = line.find("ts: ")
            t = to_seconds(line[p+4:])
            if debug:
                print("lf", id, lf, t)
            lf_l[id].append((lf, t))


    st, ts, lf = st_l, ts_l, lf_l
    # print(st)
    # print(ts)

    with open(script_log, "r") as f:
        lines = f.readlines()

    new_s = "Samples_"
    pull_s = "Pulled_"
    over_s = "Overrun_"

    n, p, o = [[], []], [[], []], [[], []]

    for line in lines:
        new_p = line.find(new_s)
        pull_p = line.find(pull_s)
        over_p = line.find(over_s)
        if new_p >= 0:
            new_p += len(new_s)
            id = int(line[new_p])
            n[id].append([float(x) for x in line[new_p + 2:].split()])
        if pull_p >= 0:
            pull_p += len(pull_s)
            id = int(line[pull_p])
            p[id].append([float(x) for x in line[pull_p + 2:].split() if x != "at"])
        if over_p >= 0:
            over_p += len(over_s)
            id = int(line[over_p])
            o[id].append([float(x) for x in line[over_p + 2:].split()])

    # print(n)
    # print(p)
    if debug:
        print(o)

    with open(script_log + ".json", "w") as f:
        d = {"st" : st, "ts" : ts, "lf" : lf, "n" : n, "p" : p, "o" : o}
        json.dump(d, f, indent=4)

def load(json_filename):
    with open(json_filename, "r") as f:
        return json.load(f)
    # return d["st"], d["ts"], d["lf"], d["n"], d["p"], d["o"]

def plot(d):
    st, ts, lf, n, p, o = d["st"], d["ts"], d["lf"], d["n"], d["p"], d["o"]

    plt.figure("v4l2src")
    for id in range(2):
        lf[id] = np.array(lf[id])
        # plt.figure(str(id))
        plt.plot(ts[id], st[id], ".-", label="good_"+str(id))
        if len(lf[id].shape) > 1:
            plt.plot(lf[id][:, 1], lf[id][:, 0], ".-", label="lost"+str(id))

    plt.legend()
    plt.tight_layout()

    plt.figure("appsink")
    for id in range(2):
        n[id], p[id], o[id] = np.array(n[id]), np.array(p[id]), np.array(o[id])
        # plt.figure(str(id))
        plt.plot(n[id][:, 1], n[id][:, 0] / 10., ".-", label="new_"+str(id))
        plt.plot(p[id][:, 2], p[id][:, 1], ".-", label="pull_"+str(id))
        if len(o[id].shape) > 1:
            plt.plot(o[id][:, 1], o[id][:, 0] / 10., ".-", label="drop_"+str(id))

    plt.legend()
    plt.tight_layout()


if __name__ == "__main__":
    gst_log = "/tmp/gst_logs"
    script_log = "/home/reip/software/experiments/log"

    # extract(gst_log, script_log, debug=True)

    script_log += "_overrun"
    
    d = load(script_log + ".json")
    plot(d)

    plt.show()

