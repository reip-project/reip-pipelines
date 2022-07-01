import cv2
from matplotlib import pyplot as plt
import numpy as np
import glob
from tqdm import tqdm
import os
from multiprocessing import Pool
import json
import pandas as pd
import shutil

root_path = '/Users/cm3580/Desktop/may_18_RH'

file_path = root_path + '/*/*/*fixed*'

file_list = sorted(glob.glob(file_path, recursive=True))

file_path = root_path + '/*/'

run_list = sorted(glob.glob(file_path))


full_dets = {}
buffer_idx = 0

df = pd.DataFrame()

for run in run_list:
    print(run)
    for det_file in tqdm(glob.glob(run + 'det/*.json')):
        vid_count = len(glob.glob(run + 'video/*fixed*', recursive=True))
        with open(det_file, 'r') as fh:
            json_obj = json.load(fh)

        for buffer in sorted(json_obj):
            if 'buffer' not in buffer:
                continue

            file_index = json_obj[buffer]['source_meta']['file_index']

            if file_index == 0 or file_index == vid_count - 1:
                continue

            vid_fname = os.path.basename(json_obj[buffer]['source_meta']['file_template']
                                         % int(json_obj[buffer]['source_meta']['file_index']))
            for det in json_obj[buffer]['objects']:
                # if det['Confidence'] < 0.7:
                #     continue
                data = {'ts': json_obj[buffer]['source_meta']['python_timestamp'],
                        'file_name': os.path.join(run, 'video', vid_fname + '.fixed.avi'),
                        'conf': det['Confidence'],
                        'left': det['Left'],
                        'right': det['Right'],
                        'top': det['Top'],
                        'bottom': det['Bottom'],
                        'label': det['Label'],
                        'frame_id': json_obj[buffer]['source_meta']['frame_id']
                        }
                df = df.append(data, ignore_index=True)

df = df.sort_values(by=['ts']).reset_index(drop=True)

img_path = os.path.join(root_path, 'images')
shutil.rmtree(img_path, ignore_errors=True)
os.makedirs(img_path, exist_ok=True)

for vid in tqdm(df['file_name'].unique()):
    vid_df = df[df['file_name'] == vid]
    vid_len = vid_df['ts'].iloc[-1] - vid_df['ts'].iloc[0]
    cap = cv2.VideoCapture(vid)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = frame_count / vid_len
    zero_frame_ts = vid_df['ts'].iloc[0]

    for frame_id in vid_df['frame_id'].unique():
        rows = vid_df[vid_df['frame_id'] == frame_id]
        frame_ts = rows['ts'].iloc[0]
        FRAME_SHIFT = 1
        frame_idx = ((frame_ts - zero_frame_ts) * fps) + FRAME_SHIFT
        first_frame_load = True
        ret = False

        rows = rows[rows['conf'] > 0.6]
        if len(rows) == 1 or not rows['label'].str.contains('car').any():
            continue

        for idx, row in rows.iterrows():

            if first_frame_load:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                first_frame_load = False
                if not ret:
                    continue
            font_scale = 2
            labelsize = cv2.getTextSize(row['label'], cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)

            start_point = (int(row['left']), int(row['top']))
            end_point = (int(row['right']), int(row['bottom']))

            label_box_start = (int(row['left']) - 4, int(row['top']) - 70)
            label_box_end = (int(row['left']) + labelsize[0][0] + 30, int(row['top']))

            text_pos = (int(row['left']) + 5, int(row['top']) - 10)

            color = (112, 194, 116)
            thickness = 8
            cv2.rectangle(frame, start_point, end_point, color, thickness)
            cv2.rectangle(frame, label_box_start, label_box_end, color, -1)
            cv2.putText(frame, row['label'].capitalize(), text_pos, cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 4, cv2.LINE_AA)

        if ret:
            cv2.imwrite(os.path.join(img_path, '%f.jpg' % frame_ts), frame)
            # frame = cv2.resize(frame, (int(2592 / 2), int(1944 / 2)))
            # cv2.imshow('REIP frame', frame)
            # cv2.waitKey()

    cap.release()