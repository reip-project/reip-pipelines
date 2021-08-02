import reip
import struct
import numpy as np


class Parser(reip.Block):
    channel_block_count = 16
    ticks_per_revolution = 90112
    range_bit_mask = 0x000FFFFF
    columns = ["r", "timestamps", "encoder", "reflectivity", "signal_photon", "noise_photon"]

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

        # self._unpack, self._trig_table = struct.Struct("<" + self.azimuth_block_fmt).unpack, None
        self._unpack = struct.Struct("<" + self.azimuth_block_fmt).unpack

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

    # def parse_frame(self, frame, resolution):
    #     """
    #     Input: data n* 85, n*16=N
    #     Returns a tuple of features:
    #     x, y, z, r, theta, refl, signal, noise, time, fid,mid, ch
    #     """
    #     encoder_block = np.tile(frame[:, 3][:, None], (1, self.channel_block_count))  # n*16
    #
    #     data_block = frame[:, 4:84].reshape((-1, len(self.channel_block_fmt)))  # N *5
    #     r = data_block[:, 0] & self.range_bit_mask
    #
    #     feat_refl, feat_signal, feat_noise = data_block[:, 1], data_block[:, 2], data_block[:, 3]
    #
    #     ret = np.stack([r, encoder_block.ravel(), feat_refl, feat_signal, feat_noise], axis=1)
    #
    #     return ret.reshape((resolution, self.channel_block_count, len(self.columns)))

    def parse_frame(self, data8, resolution):
        data = data8.view(np.uint32).reshape((-1, data8.shape[1]//4))
        # print(data8.shape, data.shape)

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

        return ret.reshape((resolution, self.channel_block_count, len(self.columns))), timestamp

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_raw"), "Invalid packet"

        # frame, timestamps = self.unpack(data)
        # timestamp = timestamps[0]
        #
        # features = self.parse_frame(frame, meta["resolution"])

        features, timestamp = self.parse_frame(data, meta["resolution"])

        meta["data_type"] = "lidar_parsed"
        meta["features"] = self.columns
        meta["timestamp"] = int(timestamp)

        return [features], meta
