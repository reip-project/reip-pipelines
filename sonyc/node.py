'''REIP SONYC Demo !!!

'''
import os
import socket
import functools
import numpy as np
import reip
import reip.blocks as B
import reip.blocks.ml
import reip.blocks.audio
import reip.blocks.encrypt
import reip.blocks.os_watch
import reip.blocks.upload

DATA_DIR = './data'
MODEL_DIR = './models'



# class Sonycnode:
#     def __init__(self, test=True, status_period=5):
#         pass
#
#     def audio(self):
#         return self
#
#     def network(self):
#         return self
#
#     def diskmonitor(self):
#         return self
#
#     def status(self):
#         return self
#
#     def file_upload(self):
#         return self
#
#     def run(self):
#         self.graph.run()

def sonyc(test=True, status_period=20):

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
    audio1s = B.audio.Mic(block_duration=1, channels=1, device="hw:2,0", dtype=np.int32)#.to(B.Debug('audio pcm'))
    # audio10s = audio1s.to(B.GatedRebuffer(functools.partial(B.temporal_coverage, 10), duration=10))
    audio10s = audio1s.to(B.FastRebuffer(size=10))

    # audio(10s) -> wav file -> encrypted -> tar.gz
    # encrypted = (
    #     audio10s
    #     .to(B.audio.AudioFile('audio/{time}.wav'))
    #     .to(B.encrypt.TwoStageEncrypt(
    #         os.path.join(DATA_DIR, 'encrypted/{time}.tar.gz'),
    #         rsa_key='test_key.pem'))
    # )

    # encrypted.to(B.TarGz('audio.gz/{time}.tar.gz'))
    # encrypted.to(B.encrypt.TwoStageDecrypt(
    #     os.path.join(DATA_DIR, 'audio.decrypt/{time}.wav'),
    #     rsa_key='test_key_private.pem'))

    (audio10s
     .to(B.audio.AudioFile(os.path.join(DATA_DIR, 'audio/{time}.wav')))
     .to(B.TarGz(os.path.join(DATA_DIR, 'audio.gz/{time}.tar.gz'))))

    # to spectrogram png
    # (audio10s
    # .to(B.audio.Stft())
    # .to(B.Debug('Spec'))
    # .to(B.audio.Specshow('data/plots/{time}.png')))

    # audio -> spl -> csv -> tar.gz
    weightings = 'ZAC'
    spl = (
        audio1s
        .to(B.audio.SPL(calibration=72.54, weighting=weightings))
        .to(B.Debug('SPL', period=status_period)))
    # write to file
    spl_headers = [f'l{w}eq' for w in weightings.lower()]
    (spl
     .to(B.Csv(os.path.join(DATA_DIR, 'spl/{time}.csv'), headers=spl_headers, max_rows=10))
     .to(B.TarGz(os.path.join(DATA_DIR, 'spl.gz/{time}.tar.gz'))))

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
                ), name='embedding-model'
            ))
            .to(B.Debug('Embedding', period=status_period))
        )
        # write to file
        (emb
         .to(B.Csv(os.path.join(DATA_DIR, 'emb/{time}.csv'), max_rows=10))
         .to(B.TarGz(os.path.join(DATA_DIR, 'emb.gz/{time}.tar.gz'))))

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
            .to(B.ml.Tflite(clsf_path, name='classification-model'))
            # .to(B.Debug('Classification', period=4))
        )
        # write to file
        (clsf
         .to(B.Csv(os.path.join(DATA_DIR, 'clsf/{time}.csv'), headers=class_names, max_rows=10))
         .to(B.TarGz(os.path.join(DATA_DIR, 'clsf.gz/{time}.tar.gz'))))

    # watch for created files
    # B.os_watch.Created('./*.gz').to(B.Debug('File Event!!'))

    # fqdn = socket.getfqdn()
    # get_upload_file_meta = lambda f, meta: {
    #     'fqdn': fqdn,
    #     'data_dir': os.path.basename(os.path.dirname(f)),
    #     'test': int(test),
    # }
    # get_upload_status_meta = lambda d, meta: {
    #     'fqdn': fqdn,
    #     'test': int(test),
    # }
    #
    # state = B.AsDict(
    #     spl_headers, class_names, max_rate=1. / 2,
    #     prepare=lambda c, x: (c, np.squeeze(np.moveaxis(x, 1, 0) if isinstance(c, (list, tuple)) else x))
    # )(spl, clsf, strategy='latest').to(B.Debug('audio analysis'))  # size=1, block=True
    # , 'embedding', emb
    # status = B.Lambda(
    #     reip.util.partial(reip.util.mergedict, lambda meta: (
    #         reip.status.base,
    #         reip.status.cpu,
    #         reip.status.memory,
    #         reip.status.network,
    #         reip.status.wifi,
    #     )), max_rate=1. / status_period,
    # ).to(B.Debug('status data'))
    # B.upload.UploadStatus(
    #     '/status', get_upload_status_meta, servers=[]
    # )(state, status)

    # watch_file = B.os_watch.Created(os.path.join(DATA_DIR, '*/*.gz')).to(B.Debug('created file'))
    # B.upload.UploadFile('/upload', get_upload_file_meta)(watch_file).to(B.Debug('upload response'))

    #NetworkSwitch([
    #    {'interface': 'wlan*', 'ssids': 'lifeline'},
    #    'eth*',  # equivalent to {'interface': 'eth*'}
    #    'ppp*',
    #    {'interface': 'wlan*'},  # implied - 'ssids': '*'
    #])

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

    reip.default_graph().run(duration=60, stats_interval=1)


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


def _chk(func):
    def inner(x, *a, **kw):
        print(func.__name__, x.shape, kw)
        _ = func(x, *a, **kw)
        print(func.__name__, _.shape)
        return _
    return inner


def test():
    with reip.Graph() as graph:
        B.dummy.Array((3, 3), max_rate=2, max_processed=10).to(B.Debug('adsf'))
        with reip.Task():
            x = B.dummy.Array((3, 3), max_rate=2, max_processed=10).to(B.Debug('adsf2')).output_stream()
    # reip.run()
    with graph.run_scope():
        for _ in reip.util.iters.throttled(interval=3):
            if any(b.done for b in graph.blocks):
                break
            graph.log.info(str(graph))



if __name__ == '__main__':
    import fire
    fire.Fire(sonyc)
