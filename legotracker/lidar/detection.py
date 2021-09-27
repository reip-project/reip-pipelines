import reip
import numpy as np
import cv2

# from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN, AgglomerativeClustering


class ObjectClustering(reip.Block):
    """
    Solutions (clustering):
    1. closing
    2. connected component
    3. KNN
    """
    count = 0
    window_size = 40
    clustering_type = "DBSCAN"

    def spatial_transformation(self, data):
        r = data[:, :, 3]
        mask = (r > 1.e-6).astype(np.uint8)
        kernel = np.ones((3, 3), np.uint8)

        erosion = cv2.erode(mask, kernel, iterations=1)
        dilation = cv2.dilate(mask, kernel, iterations=1)
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        closing = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        morpho = np.stack([mask, erosion, dilation, opening, closing], axis=2).astype(np.float32)
        res = np.concatenate([data, morpho], axis=2)

        return res

    # def spatial_clustering(self, data):
    #     resolution, channel, _ = data.shape
    #     xyz = data[:, :, :3]
    #     bg_mask = np.nonzero(data[:, :, 3] == 0)
    #
    #     if self.clustering_type == "DBSCAN":
    #         clustering = DBSCAN(eps=0.3, min_samples=10).fit(xyz.reshape(-1,3))  # eps: meter
    #     elif self.clustering_type == "Hierarchical":
    #         clustering = AgglomerativeClustering(distance_threshold=0.3)
    #
    #     labels = clustering.labels_
    #     labels[bg_mask[0],bg_mask[1]]
    #
    #     res = np.concatenate([data, labels.reshape(resolution, channel, 1)], axis=2)
    #     print(res.shape)
    #
    #     return data

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_bgfiltered"), "Invalid packet"

        features = self.spatial_transformation(data)
        meta["data_type"] = "lidar_transformed"

        return [features], meta
