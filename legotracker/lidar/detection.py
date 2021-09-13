import reip
import numpy as np


class ObjectCluster(reip.Block):
    """
    Solutions:
    1. connected component
    2. cluster
    """

    def __init__(self, **kw):
        super().__init__(**kw)

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_formatted"
                and not meta["background"]
                ), "Invalid packet"

        features, time_range = self.accumulate_frames(data, meta["timestamp"], rolled=meta["roll"])

        if features is not None:
            meta["data_type"] = "lidar_bgmask"
            meta["time_range"] = time_range

            return [features], meta
