import os
import fire
import sys
import inspect

import matplotlib.pyplot as plt

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

import cv2
import numpy as np
import reip
from dummies import BlackHole as BH
from numpy_io import NumpyWriter, NumpyReader
from plotter import Plotter
from sensor import OS1
from format import Formatter
from parse import Parser
from background import BackgroundFilter
from analyze_background import analyze_background
from detection import ObjectDetector

SENSOR_IP = "172.24.113.151"
DEST_IP = "216.165.113.240"
MODE = "1024x20"


def sensor_test():
    sensor = OS1(name="Sensor", sensor_ip=SENSOR_IP, dest_ip=DEST_IP, mode=MODE)
    sensor.to(BH(name="Sensor_BH"))


def sensor_dump():
    sensor = OS1(name="Sensor", sensor_ip=SENSOR_IP, dest_ip=DEST_IP, mode=MODE)
    writer = NumpyWriter(name="Writer", filename_template="data/dump/%d")

    sensor.to(writer).to(BH(name="Writer_BH"))


def sensor_plot():
    reader = NumpyReader(name="Reader", filename_template="data/dump/%d", max_rate=5)  # raw data
    plotter = Plotter(name="Plotter")

    reader.to(plotter, strategy="latest").to(BH(name="Plotter_BH"))


def sensor_stream(dir="/home/shuya/research/reip-pipelines/legotracker/lidar/data/lab_obj", override=False,
                  filter="/home/shuya/research/reip-pipelines/legotracker/lidar/data/lab_bg/bgmask4",
                  live=True, plot=True):
    filename = os.path.join(dir, "%d")

    if live:
        if os.path.exists(dir) and not override:
            raise RuntimeError(dir + " already exists! Set override=True to reuse?")
        reip.util.ensure_dir(filename)

        writer = NumpyWriter(name="Writer", filename_template=filename)
        with reip.Task("Stream_Task"):
            sensor = OS1(name="Sensor", sensor_ip=SENSOR_IP, dest_ip=DEST_IP, mode=MODE)
        stream = Parser(name="Parser", roll=True)(sensor) \
            .to(Formatter(name="Formatter", background=True))
        stream.to(writer).to(BH(name="Writer_BH"))
    else:
        stream = NumpyReader(name="Reader", filename_template=filename, max_rate=20//6)
        stream.id = 5500
        # stream.id = 2000

    if filter is not None:
        bg = BackgroundFilter(name="BG", filename=filter, sigma=7)
        objDetector = ObjectDetector(name="Clustering", cc_type="3D", distance=1, min_cluster_size=3)
        filtered = stream.to(bg).to(objDetector)
    else:
        filtered = stream

    if plot:
        filtered.to(Plotter(name="Plotter", type="data_type", xy=True, all=True, persist=False, savefig=False), strategy="latest")
        # filtered.to(Plotter(name="Plotter", type="data_type", xy=True, all=False, persist=False, savefig=True, out_dir=dir+"plot/"), strategy="all")

    reip.default_graph().run(duration=None, stats_interval=1)


def merge_plots(data_dir, n=1801):
    res = None

    for i in range(0, n, 5):
        if i % 20 == 0:
            print(i)
        img = cv2.imread(data_dir + "plot/%d.png" % i)
        if res is None:
            res = np.copy(img)
            continue
        idx = np.nonzero(np.sum(img, axis=2) < 3*200)
        res[idx[0], idx[1], :] = img[idx[0], idx[1], :]

    res[:90, :, :] = img[:90, :, :]

    cv2.imwrite(data_dir + "merged.png", res)
    plt.figure("Merged", (16, 12))
    plt.imshow(res[:, :, ::-1])
    plt.show()


if __name__ == '__main__':
    data_dir = "/home/vidaviz/lego/lidar/"
    # sensor_test()
    # sensor_dump()
    # sensor_plot()

    merge_plots(data_dir)

    # Record raw data
    # sensor_stream(live=True, filter=None, plot=False)

    # Analyze background
    # filename = analyze_background(plot=True)

    # Record filtered data
    # sensor_stream(live=True, filter=None, plot=False)
    # sensor_stream(live=False, filter="data/lab_bg/bgmask1", plot=True)
    # sensor_stream(live=False, dir=data_dir+"run_1/", filter=data_dir+"bg", plot=True)

    # Command line interface
    # fire.Fire()
