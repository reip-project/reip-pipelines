from __future__ import unicode_literals

import reip
import json
import time
import numpy as np

import socket
import socketserver
from socketserver import UDPServer
from os1.api import OS1API


class TempSource(reip.Block):
    def __init__(self, **kw):
        super().__init__(n_inputs=0, **kw)

    def process(self, *data, meta=None):
        data = [x for x in range(10)]
        metadata = {
            "sr": 1,
            "data_type": "temp",
        }
        return [data], metadata


class BlackHole(reip.Block):
    def __init__(self, **kw):
        # super().__init__(n_sink=0, **kw)
        super().__init__(**kw)

    def process(self, *data, meta=None):
        # raise RuntimeError("Boom")
        return None


# The original OS1 class is object, wrap it into reip.block

## 1. create empty numpy array(bytes) 2. packet-> numpy array 3. slice+binary operation-> frame id 4. fid changes return
## unpack: in formatter
class OS1(reip.Block):
    MODES = ("512x10", "512x20", "1024x10", "1024x20", "2048x10")

    def __init__(self, sensor_ip, dest_ip, packet_size=3392, azimuth_block_count=16, channel_block_count=16,
                 udp_port=7502, tcp_port=7501, mode="1024x20", **kw):
        assert mode in self.MODES, "Mode must be one of {}".format(self.MODES)
        self.dest_host = dest_ip
        self.udp_port = udp_port
        self.packet_size = packet_size
        self.mode = mode
        self.fps = int(self.mode.split("x")[1])  # default
        self.resolution = int(self.mode.split("x")[0])  # default: 1024
        self.packet_per_frame = self.resolution // 16  # default:64
        self.api = OS1API(host=sensor_ip)
        self._beam_intrinsics = None
        self._server = None

        self.azimuth_block_count = azimuth_block_count
        self.channel_block_count = channel_block_count
        self.azimuth_block_size = self.packet_size // self.azimuth_block_count  # default: 212
        self.bytesFrame = np.zeros((self.resolution, self.azimuth_block_size))  # 1024* 212 (bytes)
        self.fid = None
        self.row = 0

        super().__init__(n_inputs=0, **kw)

    def __getattr__(self, name):
        return getattr(self.api, name)

    def init(self):
        self.set_config_param("lidar_mode", self.mode)
        self.raise_for_error()
        # If we don't have a brief wait between calls the device will close the
        # TCP connection.
        time.sleep(0.1)

        self.set_config_param("udp_ip", self.dest_host)
        self.raise_for_error()
        time.sleep(0.1)

        self._beam_intrinsics = json.loads(self.get_beam_intrinsics())
        time.sleep(0.1)
        self.reinitialize()
        self.raise_for_error()
        self._beam_intrinsics = json.loads(self.get_beam_intrinsics())

        UDPServer.max_packet_size = self.packet_size
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self.dest_host, self.udp_port))
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 30000000)

    def parsePacket(self, packet):
        frame = None
        packet = np.array(bytearray(packet)).reshape((self.azimuth_block_count, -1))
        frameID = packet[:, 10:12]

        if self.fid is None:
            self.fid = frameID[0]
        boolfid = np.all(frameID == self.fid, axis=1)
        nrows = np.count_nonzero(boolfid)
        self.bytesFrame[self.row:self.row + nrows] = packet[boolfid].reshape((-1, self.azimuth_block_size))
        self.row += nrows
        # check if frame id changed, update self.bytesFrame, self.fid, self.row
        if nrows < self.azimuth_block_count:
            self.fid = frameID[boolfid == False][0]
            frame, self.bytesFrame = self.bytesFrame, np.zeros((self.resolution, self.azimuth_block_size))
            self.row = self.azimuth_block_count - nrows
            self.bytesFrame[:self.row] = packet[boolfid == False].reshape((-1, self.azimuth_block_size))
        return frame

    def process(self, *data, meta=None):
        # filename = self.template %  self.processed
        while True:
            request, addr = self._socket.recvfrom(self.packet_size)

            if len(request) == self.packet_size:
                break
        frame = self.parsePacket(request)

        metadata = {
            "sr": self.resolution * self.fps,
            "data_type": "bytes",
            "packet_size": self.resolution,
            "beam_intrinsics": self._beam_intrinsics,
        }
        if frame is not None:
            return [frame], metadata
