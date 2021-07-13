from __future__ import unicode_literals

import reip
import json
import time
import numpy as np

import socket
import socketserver
from socketserver import UDPServer
from api import OS1API


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

class OS1(reip.Block):
    MODES = ("512x10", "512x20", "1024x10", "1024x20", "2048x10")

    sensor_ip = "172.24.113.151"
    dest_ip = "216.165.113.240"
    udp_port = 7502
    tcp_port = 7501
    packet_size = 3392
    mode = "1024x20"
    azimuth_block_count = 16
    channel_block_count = 16
    api = None

    def __init__(self, **kw):
        super().__init__(n_inputs=0, **kw)
        self.api = OS1API(host=self.sensor_ip)

    def __getattr__(self, name):
        return getattr(self.api, name)

    def init(self):
        assert self.mode in self.MODES, "Mode must be one of {}".format(self.MODES)

        self.fps = int(self.mode.split("x")[1])  # default
        self.resolution = int(self.mode.split("x")[0])  # default: 1024

        self.packet_per_frame = self.resolution // self.azimuth_block_count  # default:64
        self.azimuth_block_size = self.packet_size // self.azimuth_block_count  # default: 212
        self.bytesFrame = np.zeros((self.resolution, self.azimuth_block_size), dtype=np.uint8)  # 1024* 212 (bytes)

        self.fid, self.row = None, 0
        self.sw = reip.util.Stopwatch("Packets", max_samples=1000000)

        # Init Sensor
        self.set_config_param("lidar_mode", self.mode)
        self.raise_for_error()
        # If we don't have a brief wait between calls the device will close the
        # TCP connection.
        time.sleep(0.1)

        self.set_config_param("udp_ip", self.dest_ip)
        self.raise_for_error()
        time.sleep(0.1)

        self._beam_intrinsics = json.loads(self.get_beam_intrinsics())
        time.sleep(0.1)
        self.reinitialize()
        self.raise_for_error()
        self._beam_intrinsics = json.loads(self.get_beam_intrinsics())

        # Init Server
        UDPServer.max_packet_size = self.packet_size
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self.dest_ip, self.udp_port))
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 30000000)

    def old_parsePacket(self, packet):
        # print(type(packet), len(packet), packet)
        frame = None
        packet = np.frombuffer(packet, dtype=np.uint8).reshape((self.azimuth_block_count, -1))
        # packet = np.array(bytearray(packet)).reshape((self.azimuth_block_count, -1))

        # LOOK HERE
        # mid_fid = np.frombuffer(packet[:, 8:12].tobytes(), dtype=np.uint16).reshape((-1, 2))
        # mid, fid = mid_fid[:, 0], mid_fid[:, 1]
        frameID = packet[:, 10:12]

        if self.fid is None:
            self.fid = frameID[0]
            # print(self.fid)
        boolfid = np.all(frameID == self.fid, axis=1)
        nrows = np.count_nonzero(boolfid)
        self.bytesFrame[self.row:self.row + nrows] = packet[boolfid].reshape((-1, self.azimuth_block_size),
                                                                             dtype=np.uint8)
        self.row += nrows
        # check if frame id changed, update self.bytesFrame, self.fid, self.row
        if nrows < self.azimuth_block_count:
            self.fid = frameID[boolfid == False][0]
            frame, self.bytesFrame = self.bytesFrame, np.zeros((self.resolution, self.azimuth_block_size))
            self.row = self.azimuth_block_count - nrows
            self.bytesFrame[:self.row] = packet[boolfid == False].reshape((-1, self.azimuth_block_size))
        # print(self.bytesFrame.dtype)
        return frame

    def new_parsePacket(self, packet):
        frame, fid_saved = None, None
        packet = np.frombuffer(packet, dtype=np.uint8).reshape((self.azimuth_block_count, -1))  # bytes to np.uint8

        frameID = np.frombuffer(packet[:, 10:12].tobytes(), dtype=np.uint16)
        measurementID = np.frombuffer(packet[:, 8:10].tobytes(), dtype=np.uint16)

        if self.fid is None:
            self.fid = frameID[0]
        boolfid=frameID == self.fid
        nrows = np.count_nonzero(boolfid)

        self.bytesFrame[measurementID[boolfid], :] = packet[boolfid, :].reshape((-1, self.azimuth_block_size))

        # check if frame id changed, update self.bytesFrame, self.fid, self.row
        if nrows < self.azimuth_block_count:
            fid_saved, self.fid = self.fid, frameID[frameID != self.fid][0]
            frame, self.bytesFrame = self.bytesFrame, np.zeros((self.resolution, self.azimuth_block_size),
                                                               dtype=np.uint8)

            newboolfid = frameID == self.fid
            self.bytesFrame[measurementID[newboolfid], :] = packet[newboolfid, :].reshape(
                (-1, self.azimuth_block_size))

        return frame, fid_saved

    def process(self, *data, meta=None):
        # filename = self.template %  self.processed
        while True:
            request, addr = self._socket.recvfrom(self.packet_size)

            if len(request) == self.packet_size:
                break

        frame, fid = self.new_parsePacket(request)

        if frame is not None:
            metadata = {
                "sr": self.fps,
                "fps": self.fps,
                "data_type": "lidar_raw",
                "resolution": self.resolution,
                "beam_intrinsics": self._beam_intrinsics,
                "frame_id": int(fid)
            }
            return [frame], metadata

    def finish(self):
        print("\nPackets sw:\n", self.sw)
