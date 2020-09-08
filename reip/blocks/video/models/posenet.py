import os
import cv2
import reip
import tflit
import numpy as np

class Posenet(reip.Block):
    MODEL_FILE = "models/posenet_mobilenet_v1_100_257x257_multi_kpt_stripped.tflite"
    def init(self):
        self.model = tflit.Model(os.path.join(os.path.dirname(reip.__file__), self.MODEL_FILE))
        # print(self.model.input_shape, self.model.output_shape, self.model.dtype)
        self.size = self.model.input_shape[1:-1]

    def process(self, frame, meta):
        small = cv2.resize(frame, self.size)
        X = (np.float32(small) - 127.5) / 127.5
        heat, offset = self.model.predict(X[None, ...])[:2]
        kps = parse_output(heat[0], offset[0])
        X = draw_kps(frame.copy(), kps, size=self.size)
        return [X], {}



def parse_output(heatmap_data, offset_data, threshold=0.3):

    '''
    Input:
    heatmap_data - hetmaps for an image. Three dimension array
    offset_data - offset vectors for an image. Three dimension array
    threshold - probability threshold for the keypoints. Scalar value
    Output:
    array with coordinates of the keypoints and flags for those that have
    low probability
    '''

    joint_num = heatmap_data.shape[-1]
    pose_kps = np.zeros((joint_num, 3), np.uint32)

    for i in range(heatmap_data.shape[-1]):
        joint_heatmap = heatmap_data[...,i]
        max_val_pos = np.squeeze(np.argwhere(joint_heatmap==np.max(joint_heatmap)))
        remap_pos = np.array(max_val_pos/8*257, dtype=np.int32)
        pose_kps[i, 0] = int(remap_pos[0] + offset_data[max_val_pos[0], max_val_pos[1], i])
        pose_kps[i, 1] = int(remap_pos[1] + offset_data[max_val_pos[0], max_val_pos[1], i+joint_num])
        max_prob = np.max(joint_heatmap)

        if max_prob > threshold:
            if pose_kps[i, 0] < 257 and pose_kps[i, 1] < 257:
                pose_kps[i, 2] = 1
    return pose_kps

def draw_kps(img, kps, limbs=True, face=True, size=None):
    if size:
        ratio = np.array(tuple(x/y for x, y in zip(img.shape, size)) + (1,))
        kps = (kps * ratio).astype(kps.dtype)
    for i in range(0 if face else 5, len(kps)):
        if kps[i, 2]:
            cv2.circle(img, (kps[i, 1], kps[i, 0]), 2, (0, 255, 255), -1)

    if limbs:
        for part in body_parts:
            kp1, kp2 = kps[part[0]], kps[part[1]]
            if kps[i, 2]:
                cv2.line(
                    img, (kp1[1], kp1[0]), (kp2[1], kp2[0]),
                    color=(255, 255, 255), lineType=cv2.LINE_AA,
                    thickness=1)
    return img


body_parts = [(5,6),(5,7),(6,8),(7,9),(8,10),(11,12),(5,11),(6,12),(11,13),(12,14),(13,15),(14,16)]
