import reip
import math
import struct
import numpy as np


class Formatter(reip.Block):
    def __init__(self, azimuth_block_count=16, channel_block_count=16, packet_size=3392, mode="1024x20", **kw):
        self.packet_size = packet_size
        self.ticks_per_revolution = 90112
        self.radians_360 = 2 * math.pi
        self.range_bit_mask = 0x000FFFFF
        self.azimuth_block_count = azimuth_block_count
        self.channel_block_count = channel_block_count
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
        self.packet_fmt = "<" + self.azimuth_block_fmt
        self.mode = mode
        self.fps = int(self.mode.split("x")[1])  # default
        self.resolution = int(self.mode.split("x")[0])  # default
        self.data_per_frame = self.resolution * self.channel_block_count  # default:16384
        self._trig_table = None
        self.full_columns = [
            "x",
            "y",
            "z",
            "r",  # optional
            "theta",  # optional
            "reflectivity",  # optional
            "signal_photon",  # optional
            "noise_photon",  # optional
            "timestamp",
            "frame_id",
            "measurement_id",
            "channel",
        ]

        super().__init__(**kw)

        self._unpack = struct.Struct(self.packet_fmt).unpack

    def unpack(self, rawframe):
        frame = list()
        for block in rawframe:
            block = bytes(list(map(int, block)))
            frame.append(self._unpack(block))
        frame = np.array(frame)  # 1024*85
        return frame

    def build_trig_table(self, beam_altitude_angles, beam_azimuth_angles):
        self._trig_table = []
        for i in range(self.channel_block_count):
            self._trig_table.append(
                [
                    math.sin(math.radians(beam_altitude_angles[i])),
                    math.cos(math.radians(beam_altitude_angles[i])),
                    math.radians(beam_azimuth_angles[i]),
                ]
            )
        self._trig_table = np.array(self._trig_table)  # 16 *3

    def format_frame(self, frame):
        """
        Input: data n* 85, n*16=N
        Returns a tuple of features:
        x, y, z, r, theta, refl, signal, noise, time, fid,mid, ch
        """
        feat_time = np.tile(frame[:, 0].reshape((-1, 1)), (1, self.channel_block_count)).ravel()  # N, timestamp
        feat_mid = np.tile(frame[:, 1].reshape((-1, 1)), (1, self.channel_block_count)).ravel()  # N, measurementID
        feat_fid = np.tile(frame[:, 2].reshape((-1, 1)), (1, self.channel_block_count)).ravel()  # N, frameID
        angle_block = np.tile(frame[:, 3].reshape((-1, 1)), (1, self.channel_block_count))  # n*16

        data_block = frame[:, 4:84].reshape((-1, len(self.channel_block_fmt)))  # N *5
        r = data_block[:, 0] * self.range_bit_mask / 1000  # N
        feat_refl, feat_signal, feat_noise = data_block[:, 1], data_block[:, 2], data_block[:, 3]

        n = frame.shape[0]
        feat_ch = np.array(
            [c for c in range(self.channel_block_count)] * n).ravel()  # channel

        adjusted_angle = (angle_block * self.radians_360 / self.ticks_per_revolution + np.tile(
            self._trig_table[:, 2].reshape((1, -1)), (n, 1))).ravel()  # N

        cos_angle = np.cos(adjusted_angle)  # N
        sin_angle = np.sin(adjusted_angle)  # N

        r_xy = np.multiply(r, np.tile(self._trig_table[:, 1].reshape((1, -1)), (n, 1)).ravel())  # N

        feat_x = -np.multiply(r_xy, cos_angle)  # x
        feat_y = np.multiply(r_xy, sin_angle)  # y
        feat_z = np.multiply(r, np.tile(self._trig_table[:, 0].reshape((1, -1)), (n, 1)).ravel())  # z

        return [feat_x, feat_y, feat_z, r, adjusted_angle, feat_refl, feat_signal, feat_noise, feat_time, feat_fid,
                feat_mid, feat_ch]

    def pad_frame(self):
        return

    def process(self, data, meta):
        assert (meta["data_type"] == "bytes"), "Invalid packet"
        intrinsics = meta["beam_intrinsics"]
        if self._trig_table is None:
            self.build_trig_table(intrinsics["beam_altitude_angles"], intrinsics["beam_azimuth_angles"])

        frame = self.unpack(data.tolist())
        fid = frame[0, 2]
        feature = self.format_frame(frame)
        feature = np.array(feature).T

        metadata = {
            "sr": self.data_per_frame * self.fps,
            "data_type": "format",
            "features": self.full_columns,
            "frame_id": int(fid)
        }

        return [feature], metadata