
Audio Example
===================


The full example can be found here: ...

You can run it using:

.. code-block:: bash

    python examples/sonyc_demo.py run


.. code-block:: python

    import reip
    import reip.blocks as B
    import reip.blocks.audio
    import reip.blocks.ml


First we want to capture audio from default system microphone. We'll collect it in 1 second chunks.

Then we buffer those frames into 10 second chunks while also subsampling the audio across time so that 
anyone listening to the audio wouldn't be able to string together a conversation captured by the sensor.

Here we're choosing 10 percent temporal coverage.

.. code-block:: python

    audio1s = B.audio.Mic(block_duration=1)
    audio10s = audio1s.to(
        B.GatedRebuffer(
            functools.partial(B.temporal_coverage, 10),
            size=10))

Because audio data is highly sensitive, it is unsafe to store it unencrypted on the sensor, so we 
encrypt the audio using a two-step encryption. 

We generate a new AES encryption key for each file, then encrypt the audio using that key. The key 
is then encrypted with a public key (where the private key is stored safely elsewhere for when the audio needs 
to be decrypted) and both the encrypted data and encrypted key are compressed in a tar.gz file.

To decrypt, then you just need to transfer the encrypted key to the decryptor instead of having to transfer the 
entire audio file there and back to be decrypted.

Then we print out the encrypted audio filename once it's created (using a :py:class:`reip.blocks.misc.Debug` block.)

.. code-block:: python

    encrypt_public_key = 'test_key.pem'
    if not os.path.isfile(encrypt_public_key):
        B.encrypt.create_rsa(public_fname=encrypt_public_key)

    encrypted = (
        audio10s
        .to(B.audio.AudioFile('tmp/audio/{time}.wav'))
        .to(B.encrypt.TwoStageEncrypt(
            'data/encrypted/{time}.tar.gz',
            rsa_key=encrypt_public_key))
        .to(B.Debug("Encrypted Audio", compact=True)))


Now we want to take the audio and compute the sound pressure level and write the data 
to a compressed CSV.

.. code-block:: python 

    # audio -> spl -> csv -> tar.gz
    weightings = 'ZAC'
    spl = audio1s.to(B.audio.SPL(calibration=72.54, weighting=weightings))

    # write to file
    headers = [f'l{w}eq' for w in weightings.lower()]
    spl_gz = (
        spl
        .to(B.Csv('tmp/spl/{time}.csv', headers=headers, max_rows=10))
        .to(B.TarGz('data/spl.gz/{time}.tar.gz'))
        .to(B.Debug("SPL CSV", compact=True)))


Now, finally we want to do some machine learning. We're going to spawn a Task 
so that the machine learning can occur in its own process. Everything inside of the 
``with reip.Task():`` context will run in the separate process.

The models used for SONYC sensors are released as part of the audio 
block library for your convenience. They are split into two TFLite models, 
one to compute the audio embeddings, and the other to take the embeddings 
and calculate class predictions. Once the results are saved to a CSV, their 
filenames will get printed to screen because of the ``Debug`` block.

.. code-block:: python

    # as separate process
    with reip.Task():

        # Embedding

        # audio -> embedding -> csv -> tar.gz
        emb = audio1s.to(B.audio.ml.EdgeL3())

        # write to file
        emb_gz = (
            emb
            .to(B.Csv('tmp/emb/{time}.csv', max_rows=10))
            .to(B.TarGz('data/emb.gz/{time}.tar.gz'))
            .to(B.Debug("Embedding CSV", compact=True)))

         # Classification

        # audio -> embedding -> classes -> csv -> tar.gz

        # calculate embeddings
        emb2cls = B.audio.ml.EdgeL3Embedding2Class()
        clsf = emb.to(emb2cls)

        # write to file
        clsf_gz = (
            clsf
            .to(B.Csv('tmp/clsf/{time}.csv', headers=emb2cls.classes, max_rows=10))
            .to(B.TarGz('data/clsf.gz/{time}.tar.gz'))
            .to(B.Debug("ML Classification CSV", compact=True)))

