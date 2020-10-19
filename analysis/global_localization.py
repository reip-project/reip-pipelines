import os
import json
import numpy as np
import matplotlib.pyplot as plt
from scipy import optimize


def load_edges(base_path, max_files=6, plot=True, save_plot=False):
    print("\nLoading:", base_path)
    edges, filenames = [None] * max_files, [None] * max_files

    for i in range(max_files):
        filename = base_path % (i + 1)
        if not os.path.isfile(filename):
            continue
        print(filename)
        filenames[i] = filename
        with open(filename, "r") as f:
            edges[i] = np.array(json.load(f)["edge_locations"])

    if plot:
        plt.figure(base_path, (16, 9))
        lim = 0
        for i in range(max_files):
            if edges[i] is not None:
                plt.plot(edges[i], (max_files - i) * np.ones_like(edges[i]), "x", label="Sensor "+str(i+1))
                lim = max(lim, np.max(edges[i]))
        plt.xlabel("Samples")
        plt.ylabel("Sensor")
        plt.xlim([0, lim + 10*48000])
        plt.ylim([-max_files, 2*max_files])
        plt.legend(loc="upper right")
        plt.tight_layout()
        if save_plot:
            plt.savefig(base_path[:-8] + "_edges.png", dpi=200)

    return edges, filenames


def group(edges):
    ids = np.concatenate([[i] * len(edges[i]) for i in range(6)])
    edges = np.concatenate(edges)

    order = np.argsort(edges)
    idx = np.nonzero(np.diff(edges[order]) > 48000 / 2)[0]  # 0.5 sec, ~150 m
    idx = np.concatenate(([0], idx + 1, [edges.shape[0]]))

    groups = []
    for i in range(idx.shape[0] - 1):
        s, f = idx[i], idx[i+1]
        if f - s < 4:
            print("Skipped group:", s, f)
            continue
        groups.append(np.stack([edges[order][s:f], ids[order][s:f]]).T)

    return groups


def localize(g, ref, bbox):

    def loss(x, g, ref):
        p, t = x[:3], x[3]
        r = ref[g[:, 1], :]
        dl = np.linalg.norm(r - p[None, :], axis=1)
        dt = np.abs(g[:, 0] - t) / 48000
        d = dl - dt * 330
        return np.sum(d*d)

    tm = np.min(g[:, 0])
    t0 = tm - 500
    p0 = np.average(ref, axis=0)
    print(p0, tm)
    res = optimize.minimize(loss, np.concatenate([p0, [t0]]), args=(g, ref), bounds=[*bbox, (tm - 4000, tm)])
    print(res["success"], res["x"], res["x"][3] - tm, res["x"][2] - p0[2])

    return res["x"], res["success"]


if __name__ == '__main__':
    data_path = "/home/yurii/data"
    # filegroup = "/aligned/car_buzzer_and_hummer_grid_%d.json"
    filegroup = "/aligned/sync_line_56_and_13_%d.json"

    edges, filenames = load_edges(data_path + filegroup, plot=True, save_plot=True)

    in_to_m = 0.0254
    w, h = 804 * in_to_m, 440 * in_to_m
    ref_pos = np.array([[784, 20], [785, 416], [18, 18], [18, 420], [330, 415], [330, 7]]) * in_to_m
    ref_pos = np.concatenate([ref_pos, 57 * in_to_m * np.ones((6, 1))], axis=1)
    bbox = ((0, w), (0, h), (0, 3))
    print(ref_pos)

    res = [localize(g, ref_pos, bbox) for g in group(edges)]
    pos = np.array([r[0] for r in res])
    suc = np.array([r[1] for r in res])
    suc = suc & (np.abs(pos[:, 2] - 1.45) < 0.1)
    print(suc, "\n", pos)

    plt.figure("Rooftop", (16, 9))
    plt.title(filegroup)
    for i in range(6):
        plt.plot(ref_pos[i, 0], -ref_pos[i, 1], "o", label="Sensor "+str(i+1))
    plt.plot([0, w, w, 0, 0], [0, 0, -h, -h, 0], "k", label="Rooftop")
    plt.plot(w+1, 0)  # make space for legend

    plt.plot(pos[suc, 0], -pos[suc, 1], "gx", label="Good Fit")
    plt.plot(pos[~suc, 0], -pos[~suc, 1], "rx", label="Bad Fit")

    plt.xlabel("x, meters")
    plt.ylabel("-y, meters")
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig("global_localization.png", dpi=200)

    plt.show()
