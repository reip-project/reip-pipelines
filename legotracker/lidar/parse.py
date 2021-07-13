import reip
import math
import struct
import numpy as np


class Parser(reip.Block):
    channel_block_count = 16
    ticks_per_revolution = 90112
    range_bit_mask = 0x000FFFFF

    def init(self):
        self.channel_block_fmt = (
            "I"  # Range (20 bits, 12 unused)
            "H"  # Reflectivity
            "H"  # Signal photons
            "H"  # Noise photons
            "H"  # Unused
        )
        self.azimuth_block_fmt = (
            "Q"  # Timestamp
            "H"  # Measurement ID
            "H"  # Frame ID
            "I"  # Encoder Count
            "{}"  # Channel Data
            "I"  # Status
        ).format(self.channel_block_fmt * self.channel_block_count)

        self._unpack, self._trig_table = struct.Struct("<" + self.azimuth_block_fmt).unpack, None
        self.columns = ["r", "encoder", "reflectivity", "signal_photon", "noise_photon"]
        # In the formatter block (dtype=np.float32):
        # self.columns = ["x", "y", "z", "r [meters]", "angle", "reflectivity"]

    def unpack(self, rawframe):
        n, timestamps = rawframe.shape[0], []
        frame = np.zeros((n, 85), dtype=np.uint32)

        for i in range(n):
            block = rawframe[i, :].tobytes()  # 1024*85
            unpacked = self._unpack(block)
            frame[i, :] = unpacked  # Loses timestamp info because it would require 64 bit integers
            timestamps.append(unpacked[0])
        timestamps = np.array(timestamps)

        return frame, timestamps

    def parse_frame(self, frame, resolution):
        """
        Input: data n* 85, n*16=N
        Returns a tuple of features:
        x, y, z, r, theta, refl, signal, noise, time, fid,mid, ch
        """
        # feat_time = np.repeat(frame[:, 0], self.channel_block_count)  # Wrong values (32 bits not enough)
        # feat_mid = np.repeat(frame[:, 1], self.channel_block_count)
        # feat_fid = np.repeat(frame[:, 2], self.channel_block_count)
        encoder_block = np.tile(frame[:, 3][:, None], (1, self.channel_block_count))  # n*16

        data_block = frame[:, 4:84].reshape((-1, len(self.channel_block_fmt)))  # N *5
        r = data_block[:, 0] & self.range_bit_mask
        # r = r / 1000.  # N

        feat_refl, feat_signal, feat_noise = data_block[:, 1], data_block[:, 2], data_block[:, 3]

        # cos_angle = np.cos(adjusted_angle)  # N
        # sin_angle = np.sin(adjusted_angle)  # N

        # r_xy = np.multiply(r, np.tile(self._trig_table[:, 1].reshape((1, -1)), (n, 1)).ravel())  # N

        # feat_x = -np.multiply(r_xy, cos_angle)  # x
        # feat_y = np.multiply(r_xy, sin_angle)  # y
        # feat_z = np.multiply(r, np.tile(self._trig_table[:, 0].reshape((1, -1)), (n, 1)).ravel())  # z
        ret = np.stack([r, encoder_block.ravel(), feat_refl, feat_signal, feat_noise], axis=1)

        return ret.reshape((resolution, self.channel_block_count, len(self.columns)))

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_raw"), "Invalid packet"

        frame, timestamps = self.unpack(data)
        timestamp = timestamps[0]

        features = self.parse_frame(frame, meta["resolution"])

        meta["data_type"] = "lidar_parsed"
        meta["features"] = self.columns
        meta["timestamp"] = int(timestamp)

        return [features], meta

"""
To do:
1. Framebuffer: keep order of packets 
2. Formatter -> parser:
    1). [ r, adjusted_angle, feat_refl, (feat_signal, feat_noise)]
    2) unpack --> np.frombuffer(np.uint32), then slicing for each column (might need bit mask and bit operation).
3. Formatter:
  ["x", "y", "z", "r [meters]", "angle", "reflectivity"]
"""
