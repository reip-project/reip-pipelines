import os
import json
import numpy as np
import logging

logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt

src_dir = "data/bgsrc"
save_dir = "data/bgmask"


def plot_BG(data, filename):
    ave = data[:, :, 0].T
    std = data[:, :, 1].T
    mask = data[:, :, 2].T

    plt.clf()
    plt.title(filename)

    for i, title, dat in zip(range(3), ["mean", "std", "mask"], [ave, std, mask]):
        plt.subplot(3, 1, i + 1)
        if i == 0:
            plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=50)
        if i == 1:
            plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=1)
        else:
            plt.imshow(np.repeat(dat, 3, axis=0))
        plt.title(title)
        plt.colorbar()

    plt.tight_layout()
    plt.show()


def background_detection(data):
    # Mask for valid background detection
    masks = (data > 1.e-6).astype(np.int8)
    n = np.sum(masks, axis=2)
    enough = n > (masks.shape[2] // 2)  # valid points

    sums = np.sum(np.multiply(data, masks), axis=2)
    mean = sums / n

    squares = np.sum(np.multiply(np.power(data - mean[:, :, np.newaxis], 2), masks), axis=2)
    std = np.sqrt(squares / n)
    res = np.stack([mean, std, enough.astype(np.float32)], axis=2)

    res = np.nan_to_num(res)

    return res


def analyze_background(plot=True, fidx=4, frame_range=(40, 60)):
    st, ed = frame_range
    data = np.stack([np.load(os.path.join(src_dir, "{}.npy".format(i)))[:, :, 3] for i in range(st, ed)], axis=2)

    with open(os.path.join(src_dir, "{}.json".format(st)), "r") as f:
        meta = json.load(f)
    meta["frame_range"] = frame_range

    bg_matrix = background_detection(data)

    # Save background mask
    filename = os.path.join(save_dir, "bgmask{}".format(fidx))
    with open(filename + ".npy", "wb") as f:
        np.save(f, bg_matrix)

    with open(filename + ".json", "w") as f:
        json.dump(dict(meta), f, indent=4)

    if plot:
        plot_BG(bg_matrix, "bgmask{}".format(fidx))

    return filename


if __name__ == "__main__":
    filename = analyze_background()
    print("filename", filename)
