'''REIP SONYC Demo !!!

'''
import os
import functools
import reip
import reip.blocks as B
import reip.blocks.ml
import reip.blocks.audio
import reip.blocks.audio.ml
import reip.blocks.encrypt
import reip.blocks.os_watch
import reip.blocks.upload

def run(duration=60):
    g=reip.Graph(log_level='debug').as_default()

    #######################################################
    # Graph Definition - Nothing is actually executed here.
    #######################################################

    #######################################################
    # Audio and SPL
    # 
    # What this is doing:
    #  - recording audio in 10s clips, compressing audio
    #  - plotting spectrograms
    #  - calculating spl, compressing csvs
    #######################################################

    # audio source, 1 second and 10 second chunks
    audio1s = B.audio.Mic(block_duration=1)
    audio10s = audio1s.to(
        B.GatedRebuffer(
            functools.partial(B.temporal_coverage, 10),
            size=10))

    # audio(10s) -> wav file -> encrypted -> tar.gz
    encrypt_public_key = 'scratch_data/test_key.pem'
    if not os.path.isfile(encrypt_public_key):
        B.encrypt.create_rsa(public_fname=encrypt_public_key)

    encrypted = (
        audio10s
        .to(B.audio.AudioFile('scratch_tmp/audio/{time}.wav'))
        .to(B.encrypt.TwoStageEncrypt(
            'scratch_data/encrypted/{time}.tgz',
            rsa_key=encrypt_public_key))
        .to(B.Debug("Encrypted Audio", compact=True)))

    # # to spectrogram png
    # spectrogram_pngs = (
    #     audio10s
    #     .to(B.audio.Stft())
    #     .to(B.Debug('Spec'))
    #     .to(B.audio.Specshow('data/plots/{time}.png')))

    # audio -> spl -> csv -> tar.gz
    weightings = 'ZAC'
    spl = audio1s.to(B.audio.SPL(calibration=72.54, weighting=weightings))

    # write to file
    headers = [f'l{w}eq' for w in weightings.lower()]
    spl_gz = (
        spl
        .to(B.Csv('scratch_tmp/spl/{time}.csv', headers=headers, max_rows=10))
        .to(B.TarGz('scratch_data/spl.gz/{time}.tgz'))
        .to(B.Debug("SPL CSV", compact=True)))

    #######################################################
    # Calculate Embeddings
    # 
    # What this is doing:
    #  - audio to l3 embedding, compressed csv
    #  - l3 embedding to classes, compressed csv
    #######################################################

    # as separate process
    with reip.Task(log_level='debug'):

        # Embedding

        # audio -> embedding -> csv -> tar.gz
        emb = (
            audio1s
            .to(B.audio.ml.EdgeL3())
            # .to(B.Debug('Embedding', period=4, compact=True))
        )

        # write to file
        emb_gz = (
            emb
            .to(B.Csv('scratch_tmp/emb/{time}.csv', max_rows=10))
            .to(B.TarGz('scratch_data/emb.gz/{time}.tgz'))
            .to(B.Debug("Embedding CSV", compact=True)))

         # Classification

        # audio -> embedding -> classes -> csv -> tar.gz

        # calculate embeddings
        emb2cls = B.audio.ml.EdgeL3Embedding2Class()
        clsf = (
            emb
            .to(emb2cls)
            # .to(B.Debug('Classification', period=4, compact=True))
        )

        # write to file
        clsf_gz = (
            clsf
            .to(B.Csv('scratch_tmp/clsf/{time}.csv', headers=emb2cls.classes, max_rows=10))
            .to(B.TarGz('scratch_data/clsf.gz/{time}.tgz'))
            .to(B.Debug("ML Classification CSV", compact=True)))

    # use a file scanner so that things get uploaded even 
    B.upload.UploadFilesFromDirectory(
        'https://myserver.com/upload/file', 
        'scratch_data/*/*.gz',
        fake=True)

    ###############################################################
    # Run the graph - this is where everything actually executes
    ###############################################################

    print(reip.default_graph())
    reip.run(stats_interval=20, duration=duration)



def decrypt():
    import glob
    # run this to decrypt the audio
    with reip.Graph() as g:
        (B.Iterator(glob.glob('scratch_data/encrypted/*.tgz'))
            .to(B.encrypt.TwoStageDecrypt('scratch_data/decrypted/{name}.wav', 'scratch_data/test_key_private.pem'))
            .to(B.Debug("decrypted", compact=True)))

    g.run()


if __name__ == '__main__':
    import fire
    fire.Fire()
