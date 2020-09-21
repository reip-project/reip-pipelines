import os
import glob
import time
import reip
import reip.blocks as B
# import reip.blocks.audio
from reip.blocks.video.gstreamer import GStreamer
import reip.util.gstream as gstr

os.environ['GST_DEBUG_DUMP_DOT_DIR'] = '.'


def on_split(mux, udata):
    print('split', mux, udata)

def _from_camera(gs, device, outdir='video', width=2592, height=1944, fps=15, kps=1500, duration=5):
    os.makedirs(outdir, exist_ok=True)
    name = os.path.basename(device)
    start = len(gs)
    gs.add('v4l2src', device=device)
    gs.addcap(f'image/jpeg,width={width},height={height},framerate={fps}/1')
    gs.add('jpegdec')
    gs.add('nvvidconv')
    gs.addcap('video/x-raw(memory:NVMM),format=(string)I420')
    gs.add('nvv4l2h264enc', iframeinterval=1, bitrate=kps)
    gs.addcap('video/x-h264,stream-format=(string)byte-stream')
    gs.add('h264parse')
    sink = gs.add(
        'splitmuxsink', location=os.path.join(outdir, f'out_{name}_%d.mp4'),
        max_size_time=duration * 1e9)
    # https://gstreamer.freedesktop.org/documentation/multifile/splitmuxsink.html?gi-language=c#splitmuxsink:max-size-time
    sink.connect('split-now', on_split)
    sink.connect("format-location", lambda m, id: os.path.join(outdir, f'out_{name}_{time.time():.5f}.mp4'))
    gs.link(start=start)
    return gs

# def _from_camera(gs, device=0, width=2592, height=1944, to_rgb=False, disp_width=500, fps=15):
#     start = len(gs)
#     gs.add("v4l2src", f"src_{device}", device=f"/dev/video{device}", force_aspect_ratio=True)
#     gs.addcap(f"image/jpeg,width={width},height={height},framerate={fps}/1")
#     gs.add("queue", f'queue_{device}', max_size_buffers=5, leaky='downstream')
#     gs.add("jpegdec")
#     gs.add(
#         "appsink", f"sink_{device}",
#         emit_signals=True, # eos is not processed otherwise
#         max_buffers=10, # protection from memory overflow
#         drop=False) # if python is too slow with pulling the samples
#     # gs['queue'].connect("overrun", overrun, gs['queue'])
#     # gs['sink'].connect("new-sample", new_sample, gs['sink'])
#     # if to_rgb:
#     #     start = len(gs)
#     #     gs.add("videoconvert")
#     #     gs.add("videoscale")
#     #     gs.addcap(f'video/x-raw,width={width},height={int(height/width*disp_width)},format=BGR')
#     #     gs.add(
#     #         "appsink", f"rgb_{device}",
#     #         emit_signals=True, # eos is not processed otherwise
#     #         max_buffers=10, # protection from memory overflow
#     #         drop=False) # if python is too slow with pulling the samples
#     #     gs.link(start=start)
#
#     start = len(gs)
#     gs.add("timeoverlay", f't_overlay_{device}')
#     gs.add("x264enc", key_int_max=10)
#     gs.add("h264parse")
#     gs.add("splitmuxsink", location=f'video_{device}_%02d.mov', max_size_time=10000000000, max_size_bytes=1000000)
#     gs.link(f'queue_{device}', f't_overlay_{device}')
#     gs.link(start=start)
#     return gs


def _microphone(gs, outdir='audio', duration=10):
    os.makedirs(outdir, exist_ok=True)
    start = len(gs)
    gs.add('autoaudiosrc')
    gs.add('queue', max_size_buffers=30, leaky='downstream')
    gs.add('flacenc')
    gs.add('flactag')
    flacparse = gs.add('flacparse')
    # print(list(gs))
    gs.link(start=start)

    sink = gs.add(
        "splitmuxsink",
        location=lambda m, id: os.path.join(
            outdir, f'out_mic_{time.time():.5f}.flac'),
        max_size_time=duration * 1e9,
        # async_finalize=True,
        muxer=gstr.element('matroskamux'),
    )
    sink_pad = gstr.pad('audio_0', src=True)
    sink.add_pad(sink_pad)
    # print(sink.pads)
    # print(sink.srcpads)
    # print(sink.sinkpads)
    gs.link(flacparse.name, sink.name)
    return gs


def record(**kw):
    gs = gstr.GStream()
    _microphone(gs)
    for f in glob.glob('/dev/v4l/by-path/*'):
        _from_camera(gs, f, **kw)

    with reip.Graph() as graph:
        out = GStreamer(gs, *gs.search('sink*'))
        # B.audio.Mic(duration=10).to(B.audio.AudioFile('audio/{time}.flac'))


    with graph.run_scope():
        # it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        it = reip.util.iters.loop()
        for _ in reip.util.iters.resample_iter(it, 5):
            print(graph.status())


if __name__ == '__main__':
    import fire
    fire.Fire()
