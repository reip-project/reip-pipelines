import reip
import struct
import numpy as np


class BackgroundDetector(reip.Block):
    resolution = 1024
    channel_block_count = 16
    ang = [-1.12,
           3.08,
           -1.1,
           3.08,
           -1.08,
           3.1,
           -1.06,
           3.11,
           -1.04,
           3.13,
           -1.02,
           3.16,
           -1,
           3.19,
           -0.99,
           3.22]

    def __init__(self, window_size=100, **kw):
        super().__init__(**kw)
        self.window_size = window_size
        self.count = 0
        self.frame_buffer = np.zeros((self.resolution, self.channel_block_count, self.window_size), dtype=np.float32)
        self.time_st = None
        self.std_threshold = 5

    def accumulate_frames(self, data, timestamp, rolled=False):
        """
        input: data: r, timestamps, adjusted_angle, reflectivity, signal, noise
        :return: buffer: x y z t
        """
        res, st, ed = None, None, None

        if not rolled:
            for i in range(self.channel_block_count):
                data[:, i, :] = np.roll(data[:, i, :], round(1024 * self.ang[i] / 360), axis=0)

        if self.count == 0:
            self.time_st = timestamp

        self.frame_buffer[:, :, self.count] = data[:, :, 3]
        self.count += 1

        if self.count >= self.window_size:
            bundled, self.frame_buffer = self.frame_buffer, np.zeros(
                (self.resolution, self.channel_block_count, self.window_size), dtype=np.float32)
            st, ed = self.time_st, timestamp
            self.count = 0

            res = self.background_detection(bundled)

        return res, [st, ed]

    def background_detection(self, data):
        # print(data.shape)
        coor_mean = np.mean(data, axis=-1)
        coor_std = np.std(data, axis=-1)

        bg_mask = np.zeros(coor_mean.shape)
        bg_mask[coor_std < self.std_threshold] = 1

        res = np.stack([coor_mean, coor_std, bg_mask], axis=2)

        return res

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_formatted"), "Invalid packet"

        features, time_range = self.accumulate_frames(data, meta["timestamp"], rolled=meta["roll"])

        if features is not None:
            meta["data_type"] = "lidar_bgmask"
            meta["time_range"] = time_range
            meta["std_threshold"] = self.std_threshold

            return [features], meta
