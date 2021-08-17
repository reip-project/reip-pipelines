# import reip
import logging

logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

import numpy as np
from numpy_io import NumpyReader

if __name__ == '__main__':
    reader = NumpyReader(name="Reader", filename_template="save/%d", max_rate=20)
    reader.id = 300

    for i in range(10):
        data, meta = reader.process(None)
        data = data[0]

    print(data.shape, meta)

    ang = [-1.12,
            3.08,
            -1.1,
            3.08,
            -1.08,
            3.1,
            -1.06,
            3.11,
            -1.04,
            3.13,
            -1.02,
            3.16,
            -1,
            3.19,
            -0.99,
            3.22]

    for i in range(data.shape[1]):
        data[:, i, :] = np.roll(data[:, i, :], round(1024*ang[i]/360), axis=0)
        # if i % 2 == 0:
        #     data[:, i, :] = np.roll(data[:, i, :], -3, axis=0)
        # else:
        #     data[:, i, :] = np.roll(data[:, i, :], 9, axis=0)

    # data = data[::-1, :, :]
    print(data.shape)
    r = data[:, :, 0].T / 1000
    t = data[:, :, 1].T / 1000
    e = data[:, :, 2].T
    a = data[:, :, 3].T
    s = data[:, :, 4].T
    n = data[:, :, 5].T

    # r = data[:, :, 3].T
    # t = data[:, :, 4].T / 1000

    for i, title, dat in zip(range(6), ["r", "t", "e", "a", "s", "n"], [r, t, e, a, s, n]):
        plt.subplot(6, 1, i+1)
        if i == 0:
            plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
        else:
            plt.imshow(np.repeat(dat, 3, axis=0))
        plt.title(title)
        plt.colorbar()

    # for i, title, dat in zip(range(6), ["r", "t"], [r, t]):
    #     plt.subplot(6, 1, i+1)
    #     if i == 0:
    #         plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
    #     else:
    #         plt.imshow(np.repeat(dat, 3, axis=0))
    #     plt.title(title)
    #     plt.colorbar()

    plt.tight_layout()
    plt.show()
