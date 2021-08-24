import reip
import logging
import numpy as np

logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


class Plotter(reip.Block):
    type = "2D"  # 2D or 3D
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

    def init(self):
        plt.figure(self.name, (12, 8))
        plt.clf()
        self.shown = False

    def plot_2d(self, xs):
        plt.clf()
        d = xs[0].reshape((-1, xs[0].shape[-1]))
        plt.scatter(d[:, 0], d[:, 1], c=d[:, 4], s=7, alpha=0.5, cmap='viridis')  # , vmin=-2.0, vmax=2.0)

        plt.colorbar()
        plt.xlim([-5, 50])
        plt.ylim([-5, 20])
        plt.xlim([-50, 10])
        plt.ylim([-15, 10])
        plt.title(str(self.processed))
        plt.tight_layout()
        plt.xlabel("x")
        plt.ylabel("y")

    def plot_3d(self, xs):
        plt.clf()
        ax = plt.axes(projection='3d')

        d = xs[0].reshape((-1, xs[0].shape[-1]))
        s = ax.scatter3D(d[:, 0], d[:, 1], d[:, 2], c=d[:, -2], s=7)
        ax.view_init(elev=30, azim=-120)

        plt.colorbar(s)
        plt.xlim([-5, 50])
        plt.ylim([-5, 20])
        plt.xlim([-50, 10])
        plt.ylim([-15, 10])
        ax.set_zlim([-2.5, 2])
        plt.title(str(self.processed))
        plt.tight_layout()

        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')

    def plot_img(self, xs):
        plt.clf()
        plt.title(str(self.processed))

        plt.imshow(xs[0][:, :, 0])  # , vmax=1000)

        plt.colorbar()
        plt.tight_layout()

    def plot_parsed(self, xs):

        data = xs[0]

        # for i in range(data.shape[1]):
        #     data[:, i, :] = np.roll(data[:, i, :], round(1024 * self.ang[i] / 360), axis=0)

        r = data[:, :, 0].T / 1000
        t = data[:, :, 1].T / 1000
        e = data[:, :, 2].T
        a = data[:, :, 3].T
        s = data[:, :, 4].T
        n = data[:, :, 5].T

        plt.clf()
        plt.title(str(self.processed))

        for i, title, dat in zip(range(6), ["r", "t", "e", "a", "s", "n"], [r, t, e, a, s, n]):
            plt.subplot(6, 1, i + 1)
            if i == 0:
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
            else:
                plt.imshow(np.repeat(dat, 3, axis=0))
            plt.title(title)
            plt.colorbar()

        plt.tight_layout()

    def plot_formatted(self, xs):

        data = xs[0]

        # for i in range(data.shape[1]):
        #     data[:, i, :] = np.roll(data[:, i, :], round(1024 * self.ang[i] / 360), axis=0)

        r = data[:, :, 3].T
        t = data[:, :, 4].T / 1000
        e = data[:, :, 5].T
        a = data[:, :, 6].T
        s = data[:, :, 7].T
        n = data[:, :, 8].T

        plt.clf()
        plt.title(str(self.processed))

        for i, title, dat in zip(range(6), ["r", "t", "e", "a", "s", "n"], [r, t, e, a, s, n]):
            plt.subplot(6, 1, i + 1)
            if i == 0:
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
            else:
                plt.imshow(np.repeat(dat, 3, axis=0))
            plt.title(title)
            plt.colorbar()

        plt.tight_layout()

    def plot_BG(self, xs):
        data = xs[0]

        ave = data[:, :, 0].T
        std = data[:, :, 1].T
        mask = data[:, :, 2].T

        plt.clf()
        plt.title(str(self.processed))

        for i, title, dat in zip(range(6), ["mean", "std", "mask"], [ave, std,mask]):
            plt.subplot(6, 1, i + 1)
            if i == 0:
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
            else:
                plt.imshow(np.repeat(dat, 3, axis=0))
            plt.title(title)
            plt.colorbar()

        plt.tight_layout()

    def process(self, *xs, meta=None):
        if self.type == "2D":
            self.plot_2d(xs)
        elif self.type == "3D":
            self.plot_3d(xs)
        elif self.type == "IMG":
            self.plot_img(xs)
        elif self.type == "parsed":
            self.plot_parsed(xs)
        elif self.type == "formatted":
            self.plot_formatted(xs)
        elif self.type == "BG":
            self.plot_BG(xs)
        else:
            raise RuntimeError("Unknown format")

        if not self.shown:
            plt.show(block=False)
            self.shown = True

        plt.gcf().canvas.draw()
        plt.gcf().canvas.start_event_loop(0.01)
