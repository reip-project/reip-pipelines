import reip
import numpy as np
# from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN, AgglomerativeClustering


class ObjectClustering(reip.Block):
    """
    Solutions (clustering):
    1. connected component
    2. KNN
    """
    count = 0
    window_size = 40
    clustering_type = "DBSCAN"

    def spatial_dilation(self, data):
        xyz = data[:, :, :3].reshape(-1, 3)
        return

    def spatial_clustering(self, data):
        resolution, channel, _ = data.shape
        xyz = data[:, :, :3]
        bg_mask = np.nonzero(data[:, :, 3] == 0)

        # if self.clustering_type == "DBSCAN":
        #     clustering = DBSCAN(eps=0.3, min_samples=10).fit(xyz.reshape(-1,3))  # eps: meter
        # elif self.clustering_type == "Hierarchical":
        #     clustering = AgglomerativeClustering(distance_threshold=0.3)

        # labels = clustering.labels_
        # labels[bg_mask[0],bg_mask[1]]

        # res = np.concatenate([data, labels.reshape(resolution, channel, 1)], axis=2)
        # print(res.shape)

        return data

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_bgfiltered"), "Invalid packet"

        features = self.spatial_clustering(data)
        meta["data_type"] = "lidar_clustered"

        # if features is not None:
        #     meta["data_type"] = "lidar_clustered"
        #
        #     return [data], meta
        return [data], meta
