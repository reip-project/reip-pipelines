import reip
import reip.blocks as B
import reip.status as S
import wrappingpaper as wp


################################
# General Variable Definitions
################################

class C:
    tmp_dir = '/tmp/data'
    data_dir = '/data'
    model_version = 'v3'
    servers = 'worker1', 'worker2'
    upload_server = 'https://{{ servers|choice }}.sonycproject.com' # jinja formatted

    status_interval = 3
    diskmonitor_interval = 10


# set some module-wide defaults for blocks
B.audio.spl.defaults(nfft=2048, duration=1)
B.upload.defaults(url=C.upload_server)


##############
# Audio
##############

audio = B.audio.source(channels=1, sr=48000, chunk=4800)

spl_slow = B.audio.spl()
spl_fast = B.block(spl_slow, duration=1/8.)

ml_emb = B.tflite.stft(filename='/path/to/emb_model.tf')
ml_cls = ml_emb | B.tflite(filename='/path/to/cls_model.tf')

to_status_and_csv = (
    B.X[-1] | B.add_status(),
    B.csv() | B.targz(C.data_dir),
)

##############
# Upload
##############

get_status = B.get_status(
    wifi=wp.args(interface='wlan*'),
    cell=wp.args(interface='/dev/ttyUSB2'),
    network=wp.args('wlan*', 'eth*', 'tun*'),
    usb=wp.args(
        mic_connected={'pattern': 'Cypress|JMTek', 'value': bool},
        wifi_adapter='WLAN|802.11|Wireless|wireless'),
    storage=wp.args(
        root='/', varlog='/var/log', tmp=C.tmp_dir, data=C.data_dir),
    cpu=True, memory=True,
    git='sonycnode',
)

upload_files = B.watch.create(C.data_dir) | B.upload.file('/upload') | B.rm() # ??
upload_status = B.interval(C.status_interval) | get_status | B.upload.file('/status')


##############
# Disk monitor
##############

check_usage = B.get_status(storage=C.data_dir) > B.X > 0.95
monitor_disk_usage = (
    B.interval(C.diskmonitor_interval) |
    B.while_(check_usage, B.ls(C.data_dir) | (
        B.filter.fnmatch('*/logs/*') | B.rm(),
        B.filter.fnmatch('*/data/audio/*')[::-2][:5] | B.rm(),
        B.sample(dist='left-tail')[:2] | B.filter.fnmatch('*/data/spl/*') | B.rm(),
    )))


#################
# Pipelines
#################
reip.run(
    audio=audio | (
        spl_slow | to_status_and_csv,
        spl_fast | to_status_and_csv,
        ml_emb | to_status_and_csv,
        ml_cls | to_status_and_csv,
    ),
    # or alternatively:
    # audio=audio | (x | to_status_and_csv for x in (spl_slow, spl_fast, ml_emb, ml_cls)),
    upload_files=upload_files,
    upload_status=upload_status,
    diskmonitor=monitor_disk_usage,
)
