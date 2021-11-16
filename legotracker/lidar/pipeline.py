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


def sensor_stream(live=True, filter=None, plot=True):
    if live:
        # writer = NumpyWriter(name="Writer", filename_template="data/moving3/%d")
        writer = NumpyWriter(name="Writer", filename_template="data/lab_obj/%d")
        with reip.Task("Stream_Task"):
            sensor = OS1(name="Sensor", sensor_ip=SENSOR_IP, dest_ip=DEST_IP, mode=MODE)
        stream = Parser(name="Parser", roll=True)(sensor) \
            .to(Formatter(name="Formatter", background=True))
        stream.to(writer).to(BH(name="Writer_BH"))
    else:
        # stream = NumpyReader(name="Reader", filename_template="data/moving3/%d", max_rate=20)
        stream = NumpyReader(name="Reader", filename_template="data/lab_obj/%d", max_rate=20)

    if filter is not None:
        bg = BackgroundFilter(name="BG", filename=filter, sigma=5)
        objDetector = ObjectDetector(name="Clustering", cc_type="3D", distance=1, min_cluster_size=5)
        filtered = stream.to(bg) \
            .to(objDetector)
    else:
        filtered = stream

    if plot:
        filtered.to(Plotter(name="Plotter", type="data_type", savefig=False, savegif=False), strategy="latest")


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
    sensor_stream(live=False, filter="data/lab_bg/bgmask4", plot=True)  # bgmatrix: "bg/bgmask/bgmask4"

    reip.default_graph().run(duration=None, stats_interval=1)
