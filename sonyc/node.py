'''REIP SONYC Demo !!!

'''
import os
import socket
import functools
import reip
import reip.blocks as B
import reip.blocks.ml
import reip.blocks.audio
import reip.blocks.encrypt
import reip.blocks.os_watch

MODEL_DIR = '/opt/Github/sonyc/sonycnode/models'


def sonyc(test=True):

    #######################################################
    # Graph Definition - Nothing is actually executed here.
    #######################################################

    #######################################################
    # What this is doing:
    #  - recording audio in 10s clips, compressing audio
    #  - plotting spectrograms
    #  - calculating spl, compressing csvs
    #######################################################

    # audio source, 1 second and 10 second chunks
    audio1s = B.audio.Mic(block_duration=1)
    audio10s = audio1s.to(B.GatedRebuffer(
        functools.partial(B.temporal_coverage, 10),
        duration=10))

    # audio(10s) -> wav file -> encrypted -> tar.gz
    encrypted = (
        audio10s
        .to(B.audio.AudioFile('audio/{time}.wav'))
        .to(B.encrypt.TwoStageEncrypt(
            'encrypted/{time}.tar.gz',
            rsa_key='test_key.pem')))

    encrypted.to(B.TarGz('audio.gz/{time}.tar.gz'))
    encrypted.to(B.encrypt.TwoStageDecrypt(
        'audio.decrypt/{time}.wav',
        rsa_key='test_key_private.pem'))

    (audio10s
     .to(B.audio.AudioFile('data/audio/{time}.wav'))
     .to(B.TarGz('data/audio.gz/{time}.tar.gz')))

    # to spectrogram png
    (audio10s
     .to(B.audio.Stft())
     .to(B.Debug('Spec'))
     .to(B.audio.Specshow('data/plots/{time}.png')))

    # audio -> spl -> csv -> tar.gz
    weightings = 'ZAC'
    spl = (
        audio1s
        .to(B.audio.SPL(calibration=72.54, weighting=weightings))
        .to(B.Debug('SPL', period=4)))
    # write to file
    headers = [f'l{w}eq' for w in weightings.lower()]
    (spl
     .to(B.Csv('data/spl/{time}.csv', headers=headers, max_rows=10))
     .to(B.TarGz('data/spl.gz/{time}.tar.gz')))

    #######################################################
    # What this is doing:
    #  - audio to l3 embedding, compressed csv
    #  - l3 embedding to classes, compressed csv
    #######################################################

    # as separate process
    with reip.Task():

        # Embedding

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
         .to(B.Csv('data/emb/{time}.csv', max_rows=10))
         .to(B.TarGz('data/emb.gz/{time}.tar.gz')))

         # Classification

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
         .to(B.Csv('data/clsf/{time}.csv', headers=class_names, max_rows=10))
         .to(B.TarGz('data/clsf.gz/{time}.tar.gz')))

    # watch for created files
    # B.os_watch.Created('./*.gz').to(B.Debug('File Event!!'))

    fqdn = socket.getfqdn()
    get_upload_file_meta = lambda f, meta: {
        'fqdn': fqdn,
        'data_dir': os.path.basename(os.path.dirname(f)),
        'test': int(test),
    }
    get_upload_status_meta = lambda d, meta: {
        'fqdn': fqdn,
        'test': int(test),
    }

    state = B.Dict(max_rate=1/5.)(spl, emb, clsf, strategy='latest')  # size=1, block=True
    status = B.Lambda(get_status, max_rate=1/5.)
    B.upload.UploadStatus('/status', get_upload_status_meta)(state, status)

    watch_file = B.os_watch.Created('./data/*/*.gz')
    B.upload.UploadFile('/upload', get_upload_file_meta)(watch_file)

    NetworkSwitch([
        {'interface': 'wlan*', 'ssids': 'lifeline'},
        'eth*',  # equivalent to {'interface': 'eth*'}
        'ppp*',
        {'interface': 'wlan*'},  # implied - 'ssids': '*'
    ])

    # For a full SONYC implementation
    # TODO:
    #  x stochastic audio sampling
    #  x encryption
    #  x uploader
    #  ~ status messages
    #  x disk monitor that strategically deletes files when disk gets full
    #  x sonyc lifeline detection
    #  x block logging


    ###############################################################
    # Run the graph - this is where everything actually executes
    ###############################################################

    print(reip.default_graph())
    reip.run()


import time
class NetworkSwitch(reip.Block):
    def __init__(self, config, **kw):
        self._config = config
        super().__init__(**kw)

    switch = None
    def init(self):
        import netswitch
        self.switch = netswitch.NetSwitch(self._config)

    def process(self):
        time.sleep(10)
        connected = self.switch.check()
        return [connected], {}


def get_status():
    return {}



if __name__ == '__main__':
    import fire
    fire.Fire(sonyc)