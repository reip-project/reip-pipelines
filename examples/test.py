import os
import reip
import reip.blocks as B

MODEL_DIR = '/opt/Github/sonyc/sonycnode/models'


def simple():
    (B.Interval(seconds=2)
     .to(B.audio.dummy.ExampleAudio())
     .to(B.audio.Stft())
     .to(B.Sleep())
     .to(B.Debug())
     # .to(Specshow('plots/{offset:.1f}s+{window:.1f}s-{time}.png'))
    )

    print(reip.default_graph())
    reip.default_graph().run()


def record():
    # record audio
    audio = B.audio.Mic(block_duration=10).to(B.Debug('Audio'))
    # to spectrogram
    audio.to(B.audio.Stft()).to(B.Debug('Spec')).to(B.audio.Specshow('plots/{time}.png'))
    # to audio file
    audio.to(B.audio.AudioFile('audio/{time}.wav'))

    print(reip.default_graph())
    reip.default_graph().run()

def record10s():
    # record audio and buffer into chunks of 10
    audio = B.audio.Mic(block_duration=1)
    audio10s = audio.to(B.Debug('Audio')).to(B.Rebuffer(duration=10))
    # to spectrogram
    audio10s.to(B.audio.Stft()).to(B.Debug('Spec')).to(B.Specshow('plots/{time}.png'))
    # to wavefile
    audio10s.to(B.Debug('Audio 222')).to(B.audio.AudioFile('audio/{time}.wav'))

    print(reip.default_graph())
    reip.default_graph().run()


# def record_and_spl():
#     with reip.Task() as task:
#         # audio source
#         audio = Mic(block_duration=1)
#         audio10s = audio.to(Rebuffer(duration=10))
#         # # # to spectrogram
#         # with reip.Task():
#         #     audio10s.to(Stft()).to(Specshow('plots/{time}.png'))
#         # # to wav file
#         audio10s.to(Debug('Audio 222')).to(AudioFile('audio/{time}.wav')) #.to(Encrypt()).to(TarGz()).to(Upload('/upload'))
#         # to spl -> csv -> tar.gz
#         (audio.to(SPL(calibration=72.54))
#          .to(Csv('csv/{time}.csv', max_rows=10))
#          .to(TarGz('tar/{time}.tar.gz')))
#     print(task)
#     task.run()

def record_and_spl():
    # audio source
    audio = B.audio.Mic(block_duration=1)
    audio10s = audio.to(B.Rebuffer(duration=10))
    # # # to spectrogram
    # with reip.Task():
    #     audio10s.to(B.audio.Stft()).to(B.audio.Specshow('plots/{time}.png'))
    # # to wav file
    audio10s.to(B.Debug('Audio 222')).to(B.audio.AudioFile('audio/{time}.wav'))
    #.to(Encrypt()).to(TarGz()).to(Upload('/upload'))
    # to spl -> csv -> tar.gz
    (audio.to(B.audio.SPL(calibration=72.54))
     .to(B.Csv('csv/{time}.csv', max_rows=10))
     .to(B.TarGz('tar/{time}.tar.gz')))

    print(reip.default_graph())
    reip.run()


def sonyc():
    # audio source
    audio1s = B.audio.Mic(block_duration=1)
    audio10s = audio1s.to(B.Rebuffer(duration=10))

    # audio(10s) -> wav file
    (audio10s.to(B.audio.AudioFile('audio/{time}.wav'))
     .to(B.TarGz('audio.gz/{time}.tar.gz')))

    # audio -> spl -> csv -> tar.gz
    weightings = 'ZAC'
    spl = (
        audio1s.to(B.audio.SPL(calibration=72.54, weighting=weightings))
        .to(B.Debug('SPL', period=4)))

    (spl.to(B.Csv('spl/{time}.csv', headers=[
        f'l{w}eq' for w in weightings.lower()], max_rows=10))
     .to(B.TarGz('spl.gz/{time}.tar.gz')))

    # to spectrogram png
    audio10s.to(B.audio.Stft()).to(B.Debug('Spec')).to(B.audio.Specshow('plots/{time}.png'))

    # as separate process
    with reip.Task():
        # audio -> embedding -> csv -> tar.gz
        emb_path = os.path.join(MODEL_DIR, 'quantized_default_int8.tflite')
        emb = (
            audio1s.to(B.audio.TfliteStft(emb_path))
            .to(B.Debug('Embedding', period=4)))

        (emb.to(B.Csv('emb/{time}.csv', max_rows=10))
         .to(B.TarGz('emb.gz/{time}.tar.gz')))
        # audio -> embedding -> classes -> csv -> tar.gz
        clsf_path = os.path.join(MODEL_DIR, 'mlp_ust.tflite')
        clsf = emb.to(B.Tflite(clsf_path)).to(B.Debug('Classification', period=4))
        clsf.to(B.Csv('clsf/{time}.csv', headers=[
            'engine',
            'machinery_impact',
            'non_machinery_impact',
            'powered_saw',
            'alert_signal',
            'music',
            'human_voice',
            'dog',
        ], max_rows=10)).to(B.TarGz('clsf.gz/{time}.tar.gz'))

    print(reip.default_graph())
    reip.run()


def array_task_test(exc=False, n=3):
    with reip.Task():
        x = B.dummy.SomeArray((720, 1280, 3), max_rate=n)
        # x = B.dummy.SomeArray((2, 2, 3), queue=30, blocking=True)
        # x = B.Sleep(1)(x)
        if exc:
            B.dummy.TimeBomb(3, max_rate=n)
    x = B.dummy.SomeTransform(max_rate=n)(x)#.to(B.Debug('asdf'))
    print(reip.default_graph())
    reip.run()



def status_test(exc=False, n=3):
    with reip.Task():
        x = B.dummy.SomeArray((720, 1280, 3), max_rate=n)
        # x = B.dummy.SomeArray((2, 2, 3), queue=30, blocking=True)
        # x = B.Sleep(1)(x)
        if exc:
            with reip.Graph():
                B.dummy.TimeBomb(3, max_rate=n)
    x = B.dummy.SomeTransform(max_rate=n)(x)#.to(B.Debug('asdf'))
    print(reip.default_graph())
    g = reip.default_graph()

    with g.run_scope():
        for _ in range(10):
            print(g.status())
            g.wait(1)



def camera():
    import reip.blocks.video
    with reip.Graph() as g:
        out = cam = B.video.Video(0)

    with g.run_scope():
        it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        for _ in reip.util.iters.resample_iter(it, 5):
            print(g.status())

def flow():
    import reip.blocks.video
    with reip.Graph() as g:
        cam = B.video.Video(0)
        out = flow = B.video.effects.OpticalFlow()(cam, strategy='latest')

    with g.run_scope():
        it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        for _ in reip.util.iters.resample_iter(it, 5):
            print(g.status())


def camera_rec():
    import reip.blocks.video
    with reip.Graph() as g:
        cam = B.video.Video(0)
        # show = B.video.VideoShow()(cam)
        writer = B.video.VideoWriter(
            os.path.join(os.path.dirname(__file__), 'videos/{time}.mp4'),
            duration=5, codec='avc1')(cam)
        out = B.Debug('Video Files')(writer)

    with g.run_scope():
        it = B.video.stream_imshow(cam.output_stream(strategy='latest'), 'blah')
        for _ in reip.util.iters.resample_iter(it, 5):
            print(g.status())

def pose():
    import reip.blocks.video
    from reip.blocks.video.models.posenet import Posenet
    with reip.Graph() as g:
        cam = B.video.Video(0)
        out = Posenet()(cam, strategy='latest')


    with g.run_scope():
        it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        for _ in reip.util.iters.resample_iter(it, 5):
            print(g.status())


def objects():
    import reip.blocks.video
    from reip.blocks.video.models.objects import ObjectDetection
    with reip.Graph() as g:
        cam = B.video.Video(0)
        out = ObjectDetection()(cam, strategy='latest')


    with g.run_scope():
        it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        for _ in reip.util.iters.resample_iter(it, 5):
            print(g.status())


def style():
    import reip.blocks.video
    from reip.blocks.video.models.style import StyleTransfer
    with reip.Graph() as g:
        cam = B.video.Video(0)
        out = StyleTransfer(
            os.path.join(os.path.dirname(__file__), 'js-Giddy-cropped.jpg')
        )(cam, strategy='latest')


    with g.run_scope():
        it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        for _ in reip.util.iters.resample_iter(it, 5):
            print(g.status())



def style_offline():
    import reip.blocks.video
    from reip.blocks.video.models.style import StyleTransfer
    with reip.Graph() as g:
        cam = B.video.Video(0)
        out = StyleTransfer(
            os.path.join(os.path.dirname(__file__), 'js-Giddy-cropped.jpg')
        )(cam, strategy='latest')


    with g.run_scope():
        it = B.video.stream_imshow(out.output_stream(strategy='latest'), 'blah')
        for _ in reip.util.iters.resample_iter(it, 5):
            print(g.status())

# def keras_like_interface():  # XXX: this is hypothetical
#     x = Interval()
#     x = ExampleAudio()(x)
#     x = Stft(n_fft=1024)(x)
#     x = Sleep()(x)
#     out = x = Debug()(x)
#     reip.default_graph().run()


if __name__ == '__main__':
    import fire
    fire.Fire()
