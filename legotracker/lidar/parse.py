import reip
import numpy as np


class Parser(reip.Block):
    channel_block_count = 16
    ticks_per_revolution = 90112
    range_bit_mask = 0x000FFFFF
    columns = ["r", "timestamps", "encoder", "reflectivity", "signal_photon", "noise_photon"]
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

    def __init__(self, roll=True, **kw):
        super().__init__(**kw)
        self.roll = roll

    def parse_frame(self, data8, resolution):
        data = data8.view(np.uint32).reshape((-1, data8.shape[1] // 4))

        all_timestamps = data[:, 1].astype(np.uint64) * 2 ** 32 + data[:, 0].astype(np.uint64)  # nanoseconds, (n,)
        all_timestamps = (all_timestamps // 1000000).astype(np.uint32)  # milliseconds, (n,)
        all_timestamps = np.tile(all_timestamps[:, None], (1, self.channel_block_count))  # milliseconds, (n, 16)
        timestamp = int(data[0, 1]) * 2 ** 32 + int(data[0, 0])
        # Might be zero if the packet containing first column (measurement_id=0) was lost
        # print(timestamp, all_timestamps[0])

        encoder_block = np.tile(data[:, 3][:, None], (1, self.channel_block_count))  # n*16
        data_block = data[:, 4:52].reshape((-1, 3))  # n*16*3
        r = data_block[:, 0] & self.range_bit_mask
        feat_refl = data_block[:, 1] & 0x0000FFFF
        feat_signal = np.right_shift(data_block[:, 1] & 0xFFFF0000, 16)
        feat_noise = data_block[:, 2] & 0x0000FFFF

        ret = np.stack([r, all_timestamps.ravel(), encoder_block.ravel(), feat_refl, feat_signal, feat_noise], axis=1)

        ret = ret.reshape((resolution, self.channel_block_count, len(self.columns)))
        # Roll HERE
        if self.roll:
            for i in range(self.channel_block_count):
                ret[:, i, :] = np.roll(ret[:, i, :], round(1024 * self.ang[i] / 360), axis=0)
        return ret, timestamp

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_raw"), "Invalid packet"

        features, timestamp = self.parse_frame(data, meta["resolution"])

        meta["data_type"] = "lidar_parsed"
        meta["features"] = self.columns
        meta["timestamp"] = int(timestamp)
        meta["roll"] = self.roll

        return [features], meta
