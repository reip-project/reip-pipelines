'''REIP SONYC Demo !!!

'''
import os
import functools
import reip
import reip.blocks as B
import reip.blocks.ml
import reip.blocks.audio
import reip.blocks.encrypt
import reip.blocks.os_watch

MODEL_DIR = '/opt/Github/sonyc/sonycnode/models'


class CustomBlock(reip.Block):
    def __init__(self, **kw):
        super().__init__(**kw)

    def init(self):
        pass

    def process(self, *xs, meta=None):
        return xs, meta

    def finish(self):
        pass


def sonyc():

    #######################################################
    # Graph Definition - Nothing is actually run here.
    #######################################################

    # audio source, 1 second and 10 second chunks
    audio1s = B.audio.Mic(block_duration=1)
    audio10s = audio1s.to(B.Rebuffer(duration=10))

    # audio(10s) -> wav file -> encrypted -> tar.gz
    # encrypted = (
    #     audio10s
    #     .to(B.audio.AudioFile('audio/{time}.wav'))
    #     .to(B.encrypt.TwoStageEncrypt(
    #         'encrypted/{time}.tar.gz',
    #         rsa_key='test_key.pem')))
    #
    # encrypted.to(B.TarGz('audio.gz/{time}.tar.gz'))
    # encrypted.to(B.encrypt.TwoStageDecrypt(
    #     'audio.decrypt/{time}.wav',
    #     rsa_key='test_key_private.pem'))

    (audio10s
     .to(B.audio.AudioFile('audio/{time}.wav'))
     .to(B.TarGz('audio.gz/{time}.tar.gz')))

    # to spectrogram png
    (audio10s
     .to(B.audio.Stft())
     .to(B.Debug('Spec'))
     .to(B.audio.Specshow('plots/{time}.png')))

    # audio -> spl -> csv -> tar.gz
    weightings = 'ZAC'
    spl = (
        audio1s
        .to(B.audio.SPL(calibration=72.54, weighting=weightings))
        .to(B.Debug('SPL', period=4)))
    # write to file
    headers = [f'l{w}eq' for w in weightings.lower()]
    (spl
     .to(B.Csv('spl/{time}.csv', headers=headers, max_rows=10))
     .to(B.TarGz('spl.gz/{time}.tar.gz')))


    # as separate process
    with reip.Task():
        # audio -> embedding -> csv -> tar.gz
        emb_path = os.path.join(MODEL_DIR, 'quantized_default_int8.tflite')
        emb = (
            audio1s
            .to(B.ml.Tflite(
                emb_path,
                input_features=functools.partial(
                    B.audio.ml_stft_inputs,
                    sr=8000, duration=1, hop_size=0.1, n_fft=1024,
                    n_mels=64, hop_length=160,
                )
            ))
            .to(B.Debug('Embedding', period=4)))
        # write to file
        (emb
         .to(B.Csv('emb/{time}.csv', max_rows=10))
         .to(B.TarGz('emb.gz/{time}.tar.gz')))

        # audio -> embedding -> classes -> csv -> tar.gz
        clsf_path = os.path.join(MODEL_DIR, 'mlp_ust.tflite')
        class_names = [
            'engine',
            'machinery_impact',
            'non_machinery_impact',
            'powered_saw',
            'alert_signal',
            'music',
            'human_voice',
            'dog',
        ]

        clsf = (
            emb
            .to(B.ml.Tflite(clsf_path))
            .to(B.Debug('Classification', period=4)))
        # write to file
        (clsf
         .to(B.Csv('clsf/{time}.csv', headers=class_names, max_rows=10))
         .to(B.TarGz('clsf.gz/{time}.tar.gz')))

    # watch for created files
    # B.os_watch.Created('./*.gz').to(B.Debug('File Event!!'))

    # For a full SONYC implementation
    # TODO:
    #  - stochastic audio sampling
    #  - encryption ~~
    #  - uploader
    #  - status messages
    #  - disk monitor that strategically deletes files when disk gets full
    #  - sonyc lifeline detection
    #  - block logging


    ###############################################################
    # Run the graph - this is where everything actually executes
    ###############################################################

    print(reip.Graph.default)
    reip.run()



if __name__ == '__main__':
    import fire
    fire.Fire(sonyc)
