import reip
import numpy as np


class Parser(reip.Block):
    channel_block_count = 16
    ticks_per_revolution = 90112
    range_bit_mask = 0x000FFFFF
    columns = ["r", "timestamps", "encoder", "reflectivity", "signal_photon", "noise_photon"]

    def parse_frame(self, data8, resolution):
        data = data8.view(np.uint32).reshape((-1, data8.shape[1]//4))

        # Thius didn't work because of odd number of words in one measurement block:
        # all_timestamps = data8.view(np.uint64).reshape((-1, data8.shape[1]//8))[:, 0]  # nanoseconds
        # all_timestamps = (all_timestamps // 1000000).astype(np.uint32)  # milliseconds

        all_timestamps = data[:, 1].astype(np.uint64) * 2 ** 32 + data[:, 0].astype(np.uint64)  # nanoseconds, (n,)
        all_timestamps = (all_timestamps // 1000000).astype(np.uint32)  # milliseconds, (n,)
        all_timestamps = np.tile(all_timestamps[:, None], (1, self.channel_block_count))  # milliseconds, (n, 16)
        timestamp = int(data[0, 1]) * 2**32 + int(data[0, 0])  # Might be zero if the packet containing first column (measurement_id=0) was lost
        # print(timestamp, all_timestamps[0])

        encoder_block = np.tile(data[:, 3][:, None], (1, self.channel_block_count))  # n*16
        data_block = data[:, 4:52].reshape((-1, 3))  # n*16*3
        r = data_block[:, 0] & self.range_bit_mask
        feat_refl = data_block[:, 1] & 0x0000FFFF
        feat_signal = np.right_shift(data_block[:, 1] & 0xFFFF0000, 16)
        feat_noise = data_block[:, 2] & 0x0000FFFF

        ret = np.stack([r, all_timestamps.ravel(), encoder_block.ravel(), feat_refl, feat_signal, feat_noise], axis=1)

        # Roll HERE

        return ret.reshape((resolution, self.channel_block_count, len(self.columns))), timestamp

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_raw"), "Invalid packet"

        features, timestamp = self.parse_frame(data, meta["resolution"])

        meta["data_type"] = "lidar_parsed"
        meta["features"] = self.columns
        meta["timestamp"] = int(timestamp)

        return [features], meta
