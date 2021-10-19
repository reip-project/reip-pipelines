import reip
import numpy as np
import json


# class BackgroundDetector(reip.Block):
#     """
#     1. Replace frame of missing data in buffer
#     2. build an additional mask for background filtering
#     To filter:
#     1) Undetectable data (at least in one frame):
#         Too close to sensor, have small values of range in a single frame or average
#     2) Points around the edges: high std (> 0.2 meter)---> achieved using sigma
#     """
#     resolution = 1024
#     channel_block_count = 16
#     ang = [-1.12,
#            3.08,
#            -1.1,
#            3.08,
#            -1.08,
#            3.1,
#            -1.06,
#            3.11,
#            -1.04,
#            3.13,
#            -1.02,
#            3.16,
#            -1,
#            3.19,
#            -0.99,
#            3.22]
#     count = 0
#     time_st = None
#     window_size = 40
#
#     def init(self):
#         self.frame_buffer = np.zeros((self.resolution, self.channel_block_count, self.window_size), dtype=np.float32)
#         # self.mean_threshold = 0
#         # self.std_threshold = 0.2
#
#     def accumulate_frames(self, data, timestamp, rolled=False):
#         """
#         input: data: r, timestamps, adjusted_angle, reflectivity, signal, noise
#         :return: buffer: x y z t
#         """
#         res, st, ed = None, None, None
#
#         if not rolled:
#             for i in range(self.channel_block_count):
#                 data[:, i, :] = np.roll(data[:, i, :], round(1024 * self.ang[i] / 360), axis=0)
#
#         if self.count == 0:
#             self.time_st = timestamp
#
#         self.frame_buffer[:, :, self.count] = data[:, :, 3]
#         self.count += 1
#
#         if self.count >= self.window_size:
#             bundled, self.frame_buffer = self.frame_buffer, np.zeros(
#                 (self.resolution, self.channel_block_count, self.window_size), dtype=np.float32)
#             st, ed = self.time_st, timestamp
#             self.count = 0
#
#             res = self.background_detection(bundled)
#
#         return res, [st, ed]
#
#     def background_detection(self, data):
#         # Remove undetectable data
#         # masks = (data < 1.e-6).astype(np.int8)
#         # mask = np.zeros_like(coor_mean, dtype=np.int8)
#         # for i in range(masks.shape[2]):
#         #     mask = np.bitwise_or(mask, masks[:, :, i])
#
#         # coor_mean = np.mean(data[masks_enough], axis=-1)
#         # coor_std = np.std(data, axis=-1)
#
#         # res = np.stack([coor_mean, coor_std, mask.astype(np.float32)], axis=2)
#
#         # Mask for valid background detection
#         masks = (data > 1.e-6).astype(np.int8)
#         n = np.sum(masks, axis=2)
#         enough = n > (masks.shape[2] // 2)
#
#         sums = np.sum(np.multiply(data, masks), axis=2)
#         mean = sums / n
#
#         squares = np.sum(np.multiply(np.power(data - mean, 2), masks), axis=2)
#         std = np.sqrt(squares / n)
#
#         res = np.stack([mean, std, enough.astype(np.float32)], axis=2)
#
#         return res
#
#     def process(self, data, meta):
#         assert (meta["data_type"] == "lidar_formatted"), "Invalid packet"
#
#         features, time_range = self.accumulate_frames(data, meta["timestamp"], rolled=meta["roll"])
#
#         if features is not None:
#             meta["data_type"] = "lidar_bgmask"
#             meta["time_range"] = time_range
#             meta["std_threshold"] = self.std_threshold
#
#             return [features], meta
#

class BackgroundFilter(reip.Block):
    """
    1. Background filter
        sigma'=(data-bg)/std
                if sigma' > sigma (==5): moving objects
    2. Noise filter: created in detector block
    """
    sigma = None
    noise_threshold = None
    mean_threshold = 0
    filename = "bg/bgmask/bgmask3"

    def init(self):
        # self.filename = "bg/bgmask/bgmask{:d}".format(self.fidx)
        self.bg_mask_matrix = np.load(open(self.filename + ".npy", "rb"))
        self.bg_meta = json.load(open(self.filename + ".json", "r"))
        self.bg_mean = self.bg_mask_matrix[:, :, 0]
        self.bg_std = self.bg_mask_matrix[:, :, 1]
        self.mask = self.bg_mask_matrix[:, :, 2] > 0.5  # mask of valid points
        self.idx_mask = np.nonzero(self.mask)
        self.sigma_std = self.bg_std * self.sigma

    def remove_bg(self, data):
        idx_close = np.nonzero(((self.bg_mean - data[:, :, 3]) < self.sigma_std) & self.mask)  # background mask

        data[idx_close[0], idx_close[1], :] = 0  # remove background
        # data[self.idx_mask[0], self.idx_mask[1], :] = 0  # remove noise
        # data[self.idx_mask[0], self.idx_mask[1], :] = 1 # remove noise

        return data

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_formatted"), "Invalid packet"

        features = self.remove_bg(data)

        meta["data_type"] = "lidar_bgfiltered"

        return [features], meta
