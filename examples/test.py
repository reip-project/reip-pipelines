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

    print(reip.Task.default)
    reip.Task.default.run()


def record():
    # record audio
    audio = B.audio.Mic(block_duration=10).to(B.Debug('Audio'))
    # to spectrogram
    audio.to(B.audio.Stft()).to(B.Debug('Spec')).to(B.audio.Specshow('plots/{time}.png'))
    # to audio file
    audio.to(B.audio.AudioFile('audio/{time}.wav'))

    print(reip.Graph.default)
    reip.Graph.default.run()

def record10s():
    # record audio and buffer into chunks of 10
    audio = B.audio.Mic(block_duration=1)
    audio10s = audio.to(B.Debug('Audio')).to(B.Rebuffer(duration=10))
    # to spectrogram
    audio10s.to(B.audio.Stft()).to(B.Debug('Spec')).to(B.Specshow('plots/{time}.png'))
    # to wavefile
    audio10s.to(B.Debug('Audio 222')).to(B.audio.AudioFile('audio/{time}.wav'))

    print(reip.Graph.default)
    reip.Graph.default.run()


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

    print(reip.Task.default)
    reip.run()


def sonyc():
    # audio source
    audio = B.audio.Mic(block_duration=1).to(B.Debug('Audio 1'))
    audio10s = audio.to(B.Rebuffer(duration=10))

    # audio(10s) -> wav file
    audio10s.to(B.audio.AudioFile('audio/{time}.wav')).to(B.TarGz('audio.gz/{time}.wav'))

    # # audio -> spl -> csv -> tar.gz
    # spl = audio.to(SPL(calibration=72.54)).to(Debug('SPL'))
    # spl.to(Csv('spl/{time}.csv', max_rows=10)).to(TarGz('spl.gz/{time}.tar.gz'))

    # as separate process
    with reip.Task():
        # audio -> embedding -> csv -> tar.gz
        emb = audio.to(B.Debug('Audio 2')).to(B.audio.TfliteStft(
            os.path.join(MODEL_DIR, 'quantized_default_int8.tflite'))).to(B.Debug('Embedding'))
        emb.to(B.Csv('emb/{time}.csv', max_rows=10)).to(B.TarGz('emb.gz/{time}.tar.gz'))
        # audio -> embedding -> classes -> csv -> tar.gz
        clsf = emb.to(B.Tflite(
            os.path.join(MODEL_DIR, 'mlp_ust.tflite'))).to(B.Debug('Classification'))
        clsf.to(B.Csv('clsf/{time}.csv', max_rows=10)).to(B.TarGz('clsf.gz/{time}.tar.gz'))

    print(reip.Task.default)
    reip.run()


def camera_test():
    with reip.Task():
        x = B.dummy.SomeArray((720, 1280, 3))
        # x = B.dummy.SomeArray((2, 2, 3), queue=30, blocking=True)
        # x = B.Sleep(1)(x)
    x = B.dummy.SomeTransform()(x)#.to(B.Debug('asdf'))
    print(reip.Graph.default)
    reip.run()



# def keras_like_interface():  # XXX: this is hypothetical
#     x = Interval()
#     x = ExampleAudio()(x)
#     x = Stft(n_fft=1024)(x)
#     x = Sleep()(x)
#     out = x = Debug()(x)
#     reip.Graph.default.run()


if __name__ == '__main__':
    import fire
    fire.Fire()
