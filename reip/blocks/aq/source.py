import serial
import time
import csv
import re
import reip


class Piera7100Reader:
    header = ['datetime','PC0.1','PC0.3','PC0.5','PC1.0','PC2.5','PC5.0','PC10','PM0.1','PM0.3','PM0.5','PM1.0','PM2.5','PM5.0','PM10']
    def __init__(self, port='/dev/ttyAMA0', baudrate=115200, timeout=1):
        # Setup Serial Port:
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout)

    def read(self):
        if not self.ser.readable():
            return
        line = self.ser.readline()
        if not line:
            return
        if len(re.findall('(P(C|M)\d\S\d,)', line)) < 2:
            return
        # use regex functions to format properly for csv, remove alphabetical characters
        line = re.sub('(P(C|M)10,)','', line)
        line = re.sub('(P(C|M)\d\S\d,)', '', line)
        return dict(zip(self.header, [time.strftime("%s")] + re.split(',', data)))


# def run_aq(filename="test_node-venditto-pm-{}.csv", **kw):
#     reader = AQReader(**kw)
#     while True:
#         sec_count = 0
#         fname = filename.format(time.strftime("%Y_%m_%d-%H_%M_%S"))
#         while sec_count < 60:
#             data = reader.read()
#             if not data:
#                 time.sleep(5)
#                 break

#             with open(fname, 'a') as fd:
#                 writer = csv.writer(fd)
#                 if not sec_count:
#                     writer.writerow(self.header)
#                 writer.writerow(data)
#             time.sleep(1)
#             sec_count += 1


class AQData(reip.Block):
    def __init__(self, filename, n_rows=60, max_rate=1, fail_sleep=5, **kw):
        self.filename_pattern = filename
        self.n_rows = n_rows
        self.fail_sleep = fail_sleep
        self.reader = Piera7100Reader()
        super().__init__(max_rate=max_rate, **kw)

    def init(self):
        time.sleep(10)

    def process(self, meta):
        data = self.reader.read()
        if data:
            return [data], {}
        time.sleep(self.fail_sleep - 1/max_rate)