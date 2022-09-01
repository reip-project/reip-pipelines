import reip
import numpy as np
import cv2
import copy

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from scipy.spatial.ckdtree import cKDTree
from mpl_toolkits.mplot3d import Axes3D

# from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN, AgglomerativeClustering

from labeler import labeler_module


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
    distance = 1
    subcluster = False
    count_threshold = 30
    min_cluster_size = 3

    def morphological_transformation(self, mask):
        kernel = np.ones((3, 3), np.uint8)

        erosion = cv2.erode(mask, kernel, iterations=1)
        dilation = cv2.dilate(mask, kernel, iterations=1)
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        closing = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        morpho = np.stack([mask, erosion, dilation, opening, closing], axis=2).astype(np.float32)
        # res = np.concatenate([data, morpho], axis=2)

        return morpho

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
            labels[mask.reshape(-1, ) > 0] = labels_obj
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

    def cc_labels(self, mask_r, data_r):
        labeler_module.label(mask_r, data_r, self.distance)
        return mask_r

    def spatial_detection(self, data):
        """
        1. Morphological operation: closing
        2. Connected component labelling
        3. Recover original data.
        :param data:
        :return:
        """
        r = data[:, :, 3]
        # mask = (r > 1.e-6).astype(np.uint8)
        mask = (r > 1.e-6).astype(np.uint32)

        # Morphological transformation
        if self.morph_trans:
            morph_mask = self.morphological_transformation(mask)
            closed_mask = morph_mask[:, :, -1].astype(np.uint8)

        # Connected Component labelling
        if self.cc_type == "2D":
            ret, labels = cv2.connectedComponents(copy.deepcopy(mask), connectivity=8)  # consider distance
        else:
            # xyz = data[:, :, :3]
            # labels = self.connected_component_3d(xyz, mask)
            labels = self.cc_labels(copy.deepcopy(mask), r.astype(np.double))

        xy = data[:, :, :2]
        labels = self.reassign_labels(labels, xy)

        res = np.stack([r, mask, labels, data[:, :, 0], data[:, :, 1]], axis=2)
        return res

    def reassign_labels(self, labels, xy):
        max_label = np.amax(labels)
        label_count = []

        new_labels = np.zeros(labels.shape).astype(np.uint8)
        for l in range(1, max_label + 1):
            count_ = np.count_nonzero(labels == l)
            if count_ < self.min_cluster_size:
                labels[labels == l] = 0
            else:
                label_count.append((l, count_))

        if self.subcluster:
            clustering = DBSCAN(eps=0.3, min_samples=3)
            for idx, value in enumerate(copy.deepcopy(label_count)):
                if value[1] > self.count_threshold:
                    xy_ = xy[labels == value[0], :].reshape(-1, 2)
                    clustering.fit(xy_)  # eps: meter
                    sub_clusters = clustering.labels_
                    labels[labels == value[0]] = sub_clusters + max_label + 1
                    for c in range(np.amax(sub_clusters) + 1):
                        count_ = np.count_nonzero(sub_clusters == c)
                        label_count.append((c + max_label + 1, count_))
                    label_count.remove(value)

        label_count.sort(key=lambda x: -x[1])
        for idx, value in enumerate(label_count):
            new_labels[labels == value[0]] = idx + 1

        return new_labels

    def process(self, data, meta):
        assert (meta["data_type"] == "lidar_bgfiltered"), "Invalid packet"

        features = self.spatial_detection(data)
        meta["data_type"] = "lidar_detected"

        return [features], meta
