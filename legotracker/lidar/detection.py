import reip
import numpy as np
import cv2

# from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN, AgglomerativeClustering


class ObjectDetector(reip.Block):
    """
    Solutions (clustering):
    1. closing (not use anymore)
    2. connected component 3D
    """
    count = 0
    window_size = 40
    clustering_type = "DBSCAN"

    def morphological_transformation(self, mask):
        kernel = np.ones((3, 3), np.uint8)

        erosion = cv2.erode(mask, kernel, iterations=1)
        dilation = cv2.dilate(mask, kernel, iterations=1)
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        closing = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        morpho = np.stack([mask, erosion, dilation, opening, closing], axis=2).astype(np.float32)
        # res = np.concatenate([data, morpho], axis=2)

        return morpho

    def connected_component_labelling(self, mask):
        ret, labels = cv2.connectedComponents(mask, connectivity=8)
        label_hue = np.uint8(179 * labels / np.max(labels))
        blank_ch = 255 * np.ones_like(label_hue)
        labeled_mask = cv2.merge([label_hue, blank_ch, blank_ch])
        labeled_mask = cv2.cvtColor(labeled_mask, cv2.COLOR_HSV2BGR)
        labeled_mask[label_hue == 0] = 0
        labeled_mask = cv2.cvtColor(labeled_mask, cv2.COLOR_BGR2RGB)

        return labels, labeled_mask

    def spatial_detection(self, data):
        """
        1. Morphological operation: closing
        2. Connected component labelling
        3. Recover original data.
        :param data:
        :return:
        """
        r = data[:, :, 3]
        mask = (r > 1.e-6).astype(np.uint8)

        # Morphological transformation
        # morpho_mask = self.morphological_transformation(mask)
        # closed_mask = morpho_mask[:, :, -1].astype(np.uint8)

        # Connected Component labelling
        # labels, labeled_mask = self.connected_component_labelling(closed_mask)
        # ret, labels = cv2.connectedComponents(closed_mask, connectivity=8)
        # res = np.stack([r, mask, closed_mask, labels], axis=2)
        ret, labels = cv2.connectedComponents(mask, connectivity=8) # consider distance
        res = np.stack([r, mask, mask, labels], axis=2)
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

        features = self.spatial_detection(data)
        meta["data_type"] = "lidar_detected"

        return [features], meta
