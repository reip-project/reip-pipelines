import reip
import logging
logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt


class Plotter(reip.Block):
    scatter = True  # Plot points if True

    def init(self):
        plt.figure(self.name, (12, 8))
        plt.clf()
        self.shown = False

    def process(self, *xs, meta=None):
        plt.clf()

        if self.scatter:
            plt.scatter(xs[0][:, 0], xs[0][:, 1])
        else:
            plt.imshow(xs[0])
            plt.colorbar()

        plt.title(str(self.processed))
        plt.tight_layout()

        if not self.shown:
            plt.show(block=False)
            self.shown = True

        plt.gcf().canvas.draw()
        plt.gcf().canvas.start_event_loop(0.01)
