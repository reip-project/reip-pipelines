import reip
import logging
import numpy as np

logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt
# from mpl_toolkits.mplot3d import Axes3D
# from matplotlib import animation, rc
from matplotlib.colors import ListedColormap, LinearSegmentedColormap


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
    count = 0
    version = "plot"
    savefig = False
    savegif = False

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

        for i, title, dat in zip(range(6), ["range", "timestamp", "encoder angle", "reflectivity", "signal photon",
                                            "noise photon"], [r, t, e, a, s, n]):
            plt.subplot(6, 1, i + 1)
            if i == 0:
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
            else:
                plt.imshow(np.repeat(dat, 3, axis=0))
            plt.ylabel("Channel")
            plt.xlabel("Resolution")
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

    def plot_morphological(self, xs):

        data = xs[0]

        r = data[:, :, 3].T
        m = data[:, :, -5].T
        e = data[:, :, -4].T
        d = data[:, :, -3].T
        o = data[:, :, -2].T
        c = data[:, :, -1].T

        plt.clf()
        plt.title(str(self.processed))

        for i, title, dat in zip(range(6), ["range", "mask", "erosion", "dilation", "opening", "closing"],
                                 [r, m, e, d, o, c]):
            plt.subplot(6, 1, i + 1)
            if i == 0:
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
            else:
                plt.imshow(np.repeat(dat, 3, axis=0))
            plt.ylabel("Channel")
            plt.xlabel("Resolution")
            plt.title(title)
            plt.colorbar()

        plt.tight_layout()

    def plot_ccl(self, xs):
        data = xs[0]

        r = data[:, :, 0].T
        m = data[:, :, 1].T
        c = data[:, :, 2].T
        l = data[:, :, 3].T

        plt.clf()
        plt.title(str(self.processed))

        for i, title, dat in zip(range(4), ["range", "mask", "closing", "labels"],
                                 [r, m, c, l]):
            plt.subplot(4, 1, i + 1)
            if i == 0:
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
            elif i == 3:
                colors = plt.cm.get_cmap('Set3').colors
                newColors = list(colors)
                newColors.insert(0, (0, 0, 0))
                newColorMap=ListedColormap(newColors)
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=-0.5, vmax=12.5, cmap=newColorMap)
            else:
                plt.imshow(np.repeat(dat, 3, axis=0))
            plt.ylabel("Channel")
            plt.xlabel("Resolution")
            plt.title(title)
            plt.colorbar()

        plt.tight_layout()

    def plot_cluster(self, xs):
        data = xs[0]

        distance = data[:, :, 3].T
        # labels = data[:, :, 4].T

        plt.clf()
        plt.title(str(self.processed))

        # for i, title, dat in zip(range(2), ["Distance", "Clustering"], [distance, labels]):
        #     plt.subplot(2, 1, i + 1)
        #     if i == 0:
        #         plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=50)
        #     else:
        #         plt.imshow(np.repeat(dat, 3, axis=0))
        #     plt.title(title)
        #     plt.colorbar()

        for i, title, dat in zip(range(1), ["Distance"], [distance]):
            plt.subplot(2, 1, i + 1)
            if i == 0:
                plt.imshow(np.repeat(dat, 3, axis=0), vmin=0, vmax=10)
            else:
                plt.imshow(np.repeat(dat, 3, axis=0))
            plt.title(title)
            plt.colorbar()

        plt.tight_layout()

    def process(self, *xs, meta=None):
        if self.type == "data_type":
            if meta["data_type"] == "lidar_formatted" or meta["data_type"] == "lidar_bgfiltered":
                self.type = "formatted"
            elif meta["data_type"] == "lidar_bgmask":
                self.type = "BG"
            elif meta["data_type"] == "lidar_clustered":
                self.type = "cluster"
            elif meta["data_type"] == "lidar_transformed":
                self.type = "morphological"
            elif meta["data_type"] == "lidar_detected":
                self.type = "detection"

        # animate = None

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
        elif self.type == "cluster":
            self.plot_cluster(xs)
        elif self.type == "morphological":
            self.plot_morphological(xs)
        elif self.type == "detection":
            self.plot_ccl(xs)
        else:
            raise RuntimeError("Unknown format")

        if not self.shown:
            plt.show(block=False)
            self.shown = True

        # if self.savegif:
        #     anim = animation.FuncAnimation(plt.gcf(), animate,
        #                                    frames=1000, interval=1, blit=True)
        #     anim.save("plot/{}.gif".format(self.version), writer='imagemagick', fps=20)

        plt.gcf().canvas.draw()
        plt.gcf().canvas.start_event_loop(0.001)
        if self.savefig:
            plt.savefig("plot/gif/{}_{}.png".format(self.version, self.count))
            self.count += 1
