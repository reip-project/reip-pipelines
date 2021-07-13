import reip
import logging

logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


class Plotter(reip.Block):
    scatter = True  # Plot points if True
    type = "2D"  # 2D or 3D

    def init(self):
        plt.figure(self.name, (12, 8))
        plt.clf()
        self.shown = False

    def plot_2d(self, xs):
        plt.clf()
        if self.scatter:
            plt.scatter(xs[0][:, 0], xs[0][:, 1], c=xs[0][:, 2], s=7, alpha=0.5, cmap='viridis', vmin=-2.0, vmax=2.0)
        else:
            plt.imshow(xs[0])

        plt.colorbar()
        plt.xlim([-5, 50])
        plt.ylim([-5, 20])
        plt.title(str(self.processed))
        plt.tight_layout()
        plt.xlabel("x")
        plt.ylabel("y")

    def plot_3d(self, xs):
        plt.clf()
        ax = plt.axes(projection='3d')

        ax.scatter3D(xs[0][:, 0], xs[0][:, 1], xs[0][:, 2],s=7)
        ax.view_init(elev=30, azim=-120)

        plt.xlim([-5, 50])
        plt.ylim([-5, 20])
        ax.set_zlim([-2.5, 2])
        plt.title(str(self.processed))
        plt.tight_layout()

        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')

    def plot_img(self, xs):
        plt.clf()
        plt.title(str(self.processed))

        plt.imshow(xs[0][:, :, 0])#, vmax=1000)

        plt.colorbar()
        plt.tight_layout()

    def process(self, *xs, meta=None):
        if self.type == "2D":
            self.plot_2d(xs)
        elif self.type == "3D":
            self.plot_3d(xs)
        elif self.type == "IMG":
            self.plot_img(xs)
        else:
            raise RuntimeError("Unknown format")

        if not self.shown:
            plt.show(block=False)
            self.shown = True

        plt.gcf().canvas.draw()
        plt.gcf().canvas.start_event_loop(0.01)
