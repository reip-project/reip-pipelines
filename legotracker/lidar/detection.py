import reip
import numpy as np
import cv2

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from scipy.spatial.ckdtree import cKDTree
from mpl_toolkits.mplot3d import Axes3D

# from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN, AgglomerativeClustering


class ObjectDetector(reip.Block):
    """
    Solutions (clustering):
    1. closing (not use anymore)
    2. connected component 3D: speed up
    """
    count = 0
    window_size = 40
    clustering_type = "DBSCAN"
    morph_trans = False
    cc_type = "2D"

    def morphological_transformation(self, mask):
        kernel = np.ones((3, 3), np.uint8)

        erosion = cv2.erode(mask, kernel, iterations=1)
        dilation = cv2.dilate(mask, kernel, iterations=1)
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        closing = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        morpho = np.stack([mask, erosion, dilation, opening, closing], axis=2).astype(np.float32)
        # res = np.concatenate([data, morpho], axis=2)

        return morpho

    # def connected_component_labelling(self, mask):
    #     ret, labels = cv2.connectedComponents(mask, connectivity=8)
    #     label_hue = np.uint8(179 * labels / np.max(labels))
    #     blank_ch = 255 * np.ones_like(label_hue)
    #     labeled_mask = cv2.merge([label_hue, blank_ch, blank_ch])
    #     labeled_mask = cv2.cvtColor(labeled_mask, cv2.COLOR_HSV2BGR)
    #     labeled_mask[label_hue == 0] = 0
    #     labeled_mask = cv2.cvtColor(labeled_mask, cv2.COLOR_BGR2RGB)
    #
    #     return labels, labeled_mask

    def connected_component_3d(self, xyz, mask, dist=1):
        # print('mask', sum(mask))

        xyz_obj = xyz[mask > 0].reshape(-1, 3)  # n* 3
        # print('xyz_obj', xyz_obj.shape)

        labels = np.zeros((xyz.shape[0] * xyz.shape[1], 1), np.uint8)
        labels_obj = np.zeros((len(xyz_obj), 1), np.uint8)

        # build k-d tree
        kdt = cKDTree(xyz_obj)
        edges = kdt.query_pairs(dist)  # distance in meters

        # create graph
        G = nx.from_edgelist(edges)

        # find connected components
        ccs = nx.connected_components(G)
        # node_component = {v: k for k, vs in enumerate(ccs) for v in vs}

        cluster_list = []
        for k, vs in enumerate(ccs):
            for v in vs:
                cluster_list.append((v, k))
        cluster_list.sort(key=lambda x: x[0])
        if len(cluster_list) > 0:
            cluster_list = np.array(cluster_list)
            # print('cluster_list', cluster_list.shape)
            # print('labels_obj', labels_obj.shape)
            labels_obj[cluster_list[:, 0], 0] = cluster_list[:, 1] + 1
            labels[mask.reshape(-1,) > 0] = labels_obj
        # else:
            # print('cluster_list',cluster_list)

        # visualize
        # df = pd.DataFrame(cs, columns=['x', 'y', 'z'])
        # df['c'] = pd.Series(node_component)

        # to include single-node connected components
        # df.loc[df['c'].isna(), 'c'] = df.loc[df['c'].isna(), 'c'].isna().cumsum() + df['c'].max()

        # fig = plt.figure(figsize=(10, 10))
        # ax = fig.add_subplot(111, projection='3d')
        # cmhot = plt.get_cmap("hot")
        # ax.scatter(df['x'], df['y'], df['z'], c=df['c'], s=50, cmap=cmhot)

        return labels.reshape(mask.shape)

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
        # print('mask', sum(mask))

        # Morphological transformation
        if self.morph_trans:
            morph_mask = self.morphological_transformation(mask)
            closed_mask = morph_mask[:, :, -1].astype(np.uint8)

        # Connected Component labelling
        if self.cc_type == "2D":
            ret, labels = cv2.connectedComponents(mask, connectivity=8)  # consider distance
        else:
            xyz = data[:, :, :3]
            labels = self.connected_component_3d(xyz, mask)

        res = np.stack([r, mask, labels], axis=2)
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
