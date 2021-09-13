import reip
import numpy as np
import json


class BackgroundDetector(reip.Block):
    """
    To do:
    1. Replace frame of missing data in buffer
    2. build an additional mask for background filtering
    To filter:
    1) Undetectable data:
        Too close to sensor, have small values of range in a single frame or average
    2) Points around the edges: high std (> 0.2 meter)
    """
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
        self.mean_threshold = 0
        self.std_threshold = 0.2

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

        noise_mask = np.ones(coor_mean.shape)
        # remove points around edges
        noise_mask[coor_std > self.std_threshold] = 0
        # remove undetected points
        noise_mask[coor_mean < self.mean_threshold] = 0

        res = np.stack([coor_mean, coor_std, noise_mask], axis=2)

        return res

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_formatted"), "Invalid packet"

        features, time_range = self.accumulate_frames(data, meta["timestamp"], rolled=meta["roll"])

        if features is not None:
            meta["data_type"] = "lidar_bgmask"
            meta["time_range"] = time_range
            meta["std_threshold"] = self.std_threshold

            return [features], meta


class BackgroundFilter(reip.Block):
    """
    To do:
    1. sigma'=(data-bg)/std
    if sigma' > sigma (=3): moving objects
    2. erosion: not suitable for the sparse points.
    """

    def __init__(self, q=None, sigma=None, noise_threshold=None, std_threshold=0.2, fidx=2, **kw):
        super().__init__(**kw)
        self.sigma = sigma
        self.q = q
        self.filename = "bg/bgmask/bgmask{:d}".format(fidx)
        self.bg_mask_matrix = np.load(open(self.filename + ".npy", "rb"))
        self.bg_meta = json.load(open(self.filename + ".json", "r"))
        # self.std_threshold = self.bg_meta["std_threshold"]
        self.noise_threshold = noise_threshold
        self.std_threshold = std_threshold
        self.mean_threshold = 0

    def remove_bg(self, data):
        bg_mean = self.bg_mask_matrix[:, :, 0]
        bg_std = self.bg_mask_matrix[:, :, 1]
        # if self.noise_threshold is not None:
        #     bg_std[bg_std > self.noise_threshold] = self.noise_threshold

        bg_mask = np.zeros(bg_mean.shape)
        if self.q is not None:
            self.std_threshold = np.quantile(bg_std, self.q)

        r_captured = data[:, :, 3]
        if self.sigma is None:
            bg_mask[np.absolute(r_captured - bg_mean) < self.std_threshold] = 1
        else:
            bg_mask[np.absolute(r_captured - bg_mean) / bg_std < self.sigma] = 1

        data[bg_mask == 1, :] = 0  # remove background

        # Create noise mask
        if self.noise_threshold is not None:
            # noise_mask = (~self.bg_mask_matrix[:, :, 2].astype(bool)).astype(int)
            noise_mask = np.zeros(bg_mean.shape)
            # remove points around edges
            noise_mask[bg_std > self.noise_threshold] = 1
            # remove undetected points
            noise_mask[bg_mean <= self.mean_threshold] = 1
            data[noise_mask == 1, :] = 0  # remove noise in background

        return data

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_formatted"), "Invalid packet"

        features = self.remove_bg(data)

        meta["data_type"] = "lidar_bgfiltered"

        return [features], meta
