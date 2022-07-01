import glob
import os
import subprocess
from tqdm import tqdm
import shutil
from multiprocessing import Pool

root_path = '/Users/cm3580/Desktop/may_18_RH'

file_path = root_path + '/*/*/*fixed*'

file_list = sorted(glob.glob(file_path, recursive=True))

file_path = root_path + '/*/'

run_list = sorted(glob.glob(file_path))

for run in tqdm(run_list):
    first_avi = sorted(glob.glob(run + 'video/*.avi'))[0]
    cmd = 'ffmpeg -f concat -safe 0 ' \
          '-i <(for f in %svideo/*fixed*; do echo \"file \'$f\'\"; done) -c copy %s.full.avi' % (run, first_avi)
    print(cmd)
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    process.wait()
    if process.returncode != 0:
        print('***---*** Concat failed')


