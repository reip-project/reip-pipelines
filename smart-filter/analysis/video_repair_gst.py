import glob
import os
import subprocess
from tqdm import tqdm
import shutil
from multiprocessing import Pool


def update(*a):
    pbar.update()


def repair_video(file_loc):
    img_path = os.path.join(root_path, 'images_%s' % os.path.basename(file_loc))
    shutil.rmtree(img_path, ignore_errors=True)
    os.makedirs(img_path, exist_ok=True)
    gst_path = '/Library/Frameworks/GStreamer.framework/Commands/gst-launch-1.0'
    gst_cmd = '%s filesrc location=%s ' \
              '! decodebin ' \
              '! queue ' \
              '! autovideoconvert ' \
              '! jpegenc ' \
              '! multifilesink location="%s/frame_%%d.jpg" ' % (gst_path, file_loc, img_path)
    process = subprocess.Popen(gst_cmd, shell=True, stdout=subprocess.PIPE)
    process.wait()
    if process.returncode != 0:
        print('***---*** GST extraction failed for: %s' % file_loc)
        return
    out_file_loc = file_loc + '.fixed.avi'
    gst_cmd = '%s multifilesrc location="%s/frame_%%d.jpg" ' \
              '! image/jpeg,framerate=15/1 ' \
              '! decodebin ' \
              '! theoraenc quality=48 ' \
              '! oggmux ' \
              '! filesink location="%s"' % (gst_path, img_path, out_file_loc)
    process = subprocess.Popen(gst_cmd, shell=True, stdout=subprocess.PIPE)
    process.wait()
    shutil.rmtree(img_path, ignore_errors=True)
    if process.returncode != 0:
        print('***---*** GST vid creation failed for: %s' % file_loc)
        return


root_path = '/Users/cm3580/Desktop/may_18_RH'

file_path = root_path + '/*/*/*fixed*'
for filename in glob.glob(file_path, recursive=True):
    os.remove(filename)

file_path = root_path + '/*/*/*.avi'
file_list = glob.glob(file_path, recursive=True)

pool = Pool(8)
pbar = tqdm(total=len(file_list))

for file_p in file_list:
    pool.apply_async(repair_video, args=(file_p,), callback=update)

pool.close()
pool.join()
