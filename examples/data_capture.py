import os
import re
import glob
import time
import datetime
import reip
import reip.blocks as B
import reip.blocks.audio
from reip.blocks.video.gstreamer import GStreamer
import reip.util.gstream as gstr

os.environ['GST_DEBUG_DUMP_DOT_DIR'] = '.'


DATE_FMT = '%Y-%m-%d_%H-%M-%S'


def _from_camera(gs, device, width=2592, height=1944, fps=15, outdir='video', duration=10):
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    name = os.path.basename(device).replace('/', '-')
    start = len(gs)
    # v4l2src device=/dev/video0 ! image/jpeg,width=2592,height=1944,framerate=15/1 ! tee name=t t. ! queue ! splitmuxsink muxer=avimux max-size-time=10000000000  location=test%02d.avi t. ! jpegdec ! xvimagesink -e
    gs.add("v4l2src", device=device)
    gs.addcap(f"image/jpeg,width={width},height={height},framerate={fps}/1")
    gs.add("queue", max_size_buffers=20, leaky='downstream')
    sink = gs.add(
        "splitmuxsink", muxer=gstr.element('avimux'),
        location='', max_size_time=duration * 1e9)

    sink.connect("format-location", lambda m, id:
        os.path.join(outdir, '{}_{}.avi'.format(
            name, datetime.datetime.now().strftime(DATE_FMT))))
    gs.link(start=start)


class AudioRecord(reip.ShellProcess):  # AudioRecord(channels=16, sr=48000, device='hw:2')
    _read_delay = 0.05
    def __init__(self, device, outdir='audio', fname='{}.wav'.format(DATE_FMT), channels=16, sr=48000,
                 codec='pcm_s32le', duration=10, max_rate=5, **kw):
        self.fname = fname
        self.sr, self.channels = sr, channels
        self.device, self.codec = device, codec
        self.duration = duration
        cmd = (
            'ffmpeg -f alsa -ac {ch} -ar {sr} -c:a {acodec} -i {device} '
            '-f segment -segment_time {duration} -strftime 1 {fname}'
        ).format(ch=channels, sr=sr, device=device, acodec=codec,
                 duration=duration, fname=fname)
        super().__init__(cmd, n_source=None, max_rate=max_rate, **kw)

        self._speed = re.compile(r"speed=\s*([^\s]+)x")
        self._writing = re.compile(r".*Opening '([\w\d\/\-_.]+)' for writing")

    _last_file = None
    def init(self):
        self._last_file = None
        self._meta = {}
        os.makedirs(os.path.dirname(self.fname), exist_ok=True)
        super().init()

    def process(self, meta):
        while True:
            # check if process is still open
            if self._proc.poll() is not None:
                return reip.CLOSE

            # check output line
            line = self.stderr.readline().decode('utf-8')
            if line:
                # look for file writing message
                match = self._writing.search(line)
                if match:
                    # ffmpeg prints the file when it starts writing, not when
                    # it's finished.
                    self._last_file, outf = match.groups()[0], self._last_file
                    self._meta
                    if outf:
                        return [outf], {}

                match = self._speed.search(line)
                if match:
                    self._meta['speed'] = match.groups()[0]

            time.sleep(self._read_delay)


# import ffmpeg
# class AudioRecord2(reip.Block):
#     def __init__(self, device, fname='audio/{}.wav'.format(DATE_FMT), channels=16, sr=48000,
#                  codec='pcm_s32le', duration=10, max_rate=5, **kw):
#         self.fname = fname
#         self.sr, self.channels = sr, channels
#         self.device, self.codec = device, codec
#         self.duration = duration
#         super().__init__(**kw)
#
#     def init(self):
#         self.stream = (
#             ffmpeg.input(self.device, f='alsa', ac=self.channels,
#                          ar=self.sr, acodec=self.codec)
#             .filter('segment', segment_time=self.duration, ))



def record(duration=30, channels=16, sr=48000, outdir=None, audio=True, video=True, **kw):
    outdir = outdir or 'record_{}'.format(datetime.datetime.now().strftime(DATE_FMT))
    gs = gstr.GStream()
    for f in glob.glob('/dev/v4l/by-path/*'):
        _from_camera(gs, f, duration=duration, outdir=outdir, **kw)

    with reip.Graph() as graph:
        if video:
            out = GStreamer(gs, *gs.search('sink*'))
        # B.audio.Mic('MCHStreamer', block_durationd=10).to(B.audio.AudioFile('audio/{time}.wav')).to(B.Debug('audio file'))
        if audio:
            AudioRecord(
                'hw:2', outdir=outdir, duration=duration, channels=channels, sr=sr
            ).to(B.Debug('audio record'))

    with graph.run_scope():
        # it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        it = reip.util.iters.loop()
        for _ in reip.util.iters.resample_iter(it, 5):
            print(graph.status())


if __name__ == '__main__':
    import fire
    fire.Fire(record)
