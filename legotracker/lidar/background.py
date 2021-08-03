import reip
import struct
import numpy as np


class BackgroundDetector(reip.Block):
    resolution = 1024
    channel_block_count = 16

    def __init__(self, window_size=100, **kw):
        super().__init__(**kw)
        self.window_size = window_size
        self.count = 0
        self.frame_buffer = np.zeros((self.resolution, self.channel_block_count, 3, self.window_size), dtype=np.float32)

    def accumulate_frames(self, data):
        """
        input: data: x, y, z, r, timestamps, adjusted_angle, reflectivity, signal, noise
        :return: buffer: x y z t
        """
        # coor_xyz = data[:, :3]
        while self.count < self.window_size:
            self.frame_buffer[:, :, :, self.count] = data[:, :, :3]
            self.count += 1
        bundle, self.frame_buffer = self.frame_buffer, np.zeros((self.resolution, self.channel_block_count,  3, self.window_size))
        self.count = 0
        res = self.background_detection(bundle)
        return res

    def background_detection(self, data):
        coor_mean = np.mean(data, axis=-1)
        coor_std = np.std(data, axis=-1)
        # print(coor_std.shape)

        # res = [coor_mean, coor_std]
        return coor_std

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_formatted"), "Invalid packet"

        features = self.accumulate_frames(data)

        meta["data_type"] = "lidar_bundled"

        return [features], meta
