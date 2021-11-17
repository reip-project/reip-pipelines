import os
import fire
import sys
import inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

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
        stream = NumpyReader(name="Reader", filename_template=filename, max_rate=20)

    if filter is not None:
        bg = BackgroundFilter(name="BG", filename=filter, sigma=5)
        objDetector = ObjectDetector(name="Clustering", cc_type="3D", distance=1, min_cluster_size=5)
        filtered = stream.to(bg) \
            .to(objDetector)
    else:
        filtered = stream

    if plot:
        filtered.to(Plotter(name="Plotter", type="data_type", savefig=False, savegif=False), strategy="latest")

    reip.default_graph().run(duration=None, stats_interval=1)


if __name__ == '__main__':
    # sensor_test()
    # sensor_dump()
    # sensor_plot()

    # Record raw data
    # sensor_stream(live=True, filter=None, plot=False)

    # Analyze background
    # filename = analyze_background(plot=True)

    # Record filtered data
    # sensor_stream(live=True, filter=None, plot=False)
    # sensor_stream(live=False, filter="data/lab_bg/bgmask1", plot=True)

    # Command line interface
    fire.Fire()
