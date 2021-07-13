import reip
import math
import struct
import numpy as np


class Formatter(reip.Block):
    channel_block_count = 16
    ticks_per_revolution = 90112
    radians_360 = 2 * math.pi
    resolution = None
    _trig_table = None

    def __init__(self,  **kw):
        self.columns = ["x", "y", "z", "r", "angle""reflectivity"]

        super().__init__(**kw)

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
        Input shape: resolution * 16 * 5
        Input columns: r, encoder_angle, reflectivity, signal photon, noise photon

        Returns columns: x, y, z, r, angle. reflectivity
        """
        r = frame[:, :, 0].astype(np.float32) / 1000 # n * 16

        encoder_block = frame[:, :, 1]
        adjusted_angle = (encoder_block * self.radians_360 / self.ticks_per_revolution + np.tile(
            self._trig_table[:, 2].reshape((1, -1)), (self.resolution, 1))).ravel()  # N

        cos_angle = np.cos(adjusted_angle)  # N
        sin_angle = np.sin(adjusted_angle)  # N

        reflectivity = frame[:, :, 2].ravel()

        r_xy = np.multiply(r, np.tile(self._trig_table[:, 1].reshape((1, -1)), (self.resolution, 1))).ravel()  # N

        x = -np.multiply(r_xy, cos_angle)  # x: (N,)
        y = np.multiply(r_xy, sin_angle)
        z = np.multiply(r, np.tile(self._trig_table[:, 0].reshape((1, -1)), (self.resolution, 1)).ravel())

        ret = np.stack([x, y, z, r, adjusted_angle, reflectivity], axis=1)

        return ret.reshape((self.resolution, self.channel_block_count, len(self.columns)))

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_parsed"), "Invalid packet"
        intrinsics = meta["beam_intrinsics"]
        if self._trig_table is None:
            self.build_trig_table(intrinsics["beam_altitude_angles"], intrinsics["beam_azimuth_angles"])
        self.resolution = meta["resolution"]

        feature = self.format_frame(data)

        meta["data_type"] = "lidar_formatted"
        meta["features"] = self.columns

        return [feature], meta
