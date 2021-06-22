import reip

from dummies import BlackHole as BH
from numpy_io import NumpyWriter, NumpyReader
from plotter import Plotter
from sensor import OS1
from format import Formatter

SENSOR_IP = "172.24.113.151"
DEST_IP = "216.165.113.240"
MODE = "1024x20"


def sensor_test():
    sensor = OS1(name="Sensor", sensor_ip=SENSOR_IP, dest_ip=DEST_IP, mode=MODE)
    sensor.to(BH(name="Sensor_BH"))


def sensor_dump():
    sensor = OS1(name="Sensor", sensor_ip=SENSOR_IP, dest_ip=DEST_IP, mode=MODE)
    writer = NumpyWriter(name="Writer", filename_template="dump/%d")

    sensor.to(writer).to(BH(name="Writer_BH"))


def sensor_plot():
    reader = NumpyReader(name="Reader", filename_template="dump/%d", max_rate=5)
    plotter = Plotter(name="Plotter")

    reader.to(plotter, strategy="latest").to(BH(name="Plotter_BH"))


def sensor_stream(live=True, plot=True):
    if live:
        with reip.Task("Stream_Task"):
            sensor = OS1(name="Sensor", sensor_ip=SENSOR_IP, dest_ip=DEST_IP, mode=MODE)
        stream = Formatter(name="Formatter")(sensor)
    else:
        stream = NumpyReader(name="Reader", filename_template="save/%d", max_rate=20)

    writer = NumpyWriter(name="Writer", filename_template="save/%d")
    stream.to(writer).to(BH(name="Writer_BH"))

    if plot:
        stream.to(Plotter(name="Plotter", scatter=True), strategy="latest")


if __name__ == '__main__':
    # sensor_test()
    # sensor_dump()
    # sensor_plot()

    sensor_stream(live=True, plot=True)

    reip.default_graph().run(duration=None, stats_interval=1)