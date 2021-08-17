import reip
import numpy as np


class Formatter(reip.Block):
    channel_block_count = 16
    ticks_per_revolution = 90112
    trig_table = None
    columns = ["x", "y", "z", "r", "timestamps", "angle", "reflectivity", "signal_photon", "noise_photon"]

    def format_frame(self, frame, resolution, n):
        """
        Input shape: resolution * channel_block_count * 5
        Input columns: r, timestamps, encoder_angle, reflectivity, signal photon, noise photon

        Return shape: resolution * channel_block_count * 6
        Returns columns: x, y, z, r, timestamps, angle. reflectivity
        """
        assert self.channel_block_count == frame.shape[1], "Invalid number of channels"

        r = frame[:, :, 0].ravel().astype(np.float32) / 1000  # (resolution * self.channel_block_count,)

        timestamps = frame[:, :, 1].ravel()  # (resolution * self.channel_block_count,)
        encoder_block = frame[:, :, 2].ravel()  # (resolution * self.channel_block_count,)
        reflectivity = frame[:, :, 3].ravel()  # (resolution * self.channel_block_count,)
        signal = frame[:, :, 4].ravel()  # (resolution * self.channel_block_count,)
        noise = frame[:, :, 5].ravel()  # (resolution * self.channel_block_count,)

        # adjusted_angle = 2 * np.pi * (1 - encoder_block / self.ticks_per_revolution) + \
        #                     np.tile(self.trig_table[:, 2].ravel(), (resolution,))

        encoder_angle = 2 * np.pi * (1 - encoder_block / self.ticks_per_revolution)
        adjusted_angle = encoder_angle - np.tile(self.trig_table[:, 2].ravel(), (resolution,))  # encoder+ azimuth

        r_xy = r * np.tile(self.trig_table[:, 1].ravel(), (resolution,))

        # x, y = -r_xy * np.cos(adjusted_angle), r_xy * np.sin(adjusted_angle) # assume orgin n= 0 mm
        x = r_xy * np.cos(adjusted_angle) + n * np.cos(encoder_angle)
        y = r_xy * np.sin(adjusted_angle) + n * np.sin(encoder_angle)

        # z = (r - n) * np.tile(self.trig_table[:, 0].ravel(), (resolution,))
        z = r * np.tile(self.trig_table[:, 0].ravel(), (resolution,))


        ret = np.stack([x, y, z, r, timestamps, adjusted_angle, reflectivity, signal, noise], axis=1)

        return ret.reshape((resolution, self.channel_block_count, len(self.columns)))

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_parsed"), "Invalid packet"
        intrinsics = meta["beam_intrinsics"]

        if self.trig_table is None:
            alt, azim = np.radians(intrinsics["beam_altitude_angles"]), np.radians(intrinsics["beam_azimuth_angles"])
            self.trig_table = np.array(
                [[np.sin(alt[i]), np.cos(alt[i]), azim[i]] for i in range(self.channel_block_count)])

        features = self.format_frame(data, meta["resolution"], intrinsics["lidar_origin_to_beam_origin_mm"] / 1000)

        meta["data_type"] = "lidar_formatted"
        meta["features"] = self.columns

        return [features], meta
