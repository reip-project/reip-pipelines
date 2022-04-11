REIP: IoT Data Pipelines
================================

REIP is a reconfigurable framework that allows users to quickly build data streaming pipelines for IoT-based sensor research projects.

It is designed for mid-tier IoT devices that are small enough to be placed in the field, but still can run more complex operations like video processing and machine learning.

.. This introduces a number of complications around performing performing 

.. Concepts
.. ========
..  - **Pipeline**: An end-to-end workflow. It should have a driving block (source) that will run the downstream processing blocks. A project will typically consist of multiple pipelines that implement different pieces of functionality.
..  - **Components**: A reusable combination/chain of blocks
..  - **Blocks**: An atomic piece of code that consists of initialization and a transformation function with a variable number of inputs and outputs.


Quickstart
---------------


Chain Interface -- Javascript-esque method chaining.

.. code-block:: python

   import reip
   import reip.blocks as B
   import reip.blocks.audio

   # Define your pipeline
   ########################

   # record audio and buffer into chunks of 10
   audio = B.audio.Mic(block_duration=1)
   audio10s = (
      audio.to(B.Debug('Audio'))
      .to(B.Rebuffer(duration=10)))
   # plot a spectrogram
   spec_img = (
      audio10s.to(B.audio.Stft())
      .to(B.Debug('Spec'))
      .to(B.Specshow('plots/{time}.png')))
   # to wavefile
   wav = (
      audio10s.to(B.Debug('Audio 222'))
      .to(B.audio.AudioFile('audio/{time}.wav')))

   # Execute your pipeline
   ########################

   reip.default_graph().run()


Function Interface - Mimicking a Keras interface.

.. code-block:: python

   # Define your pipeline
   ########################

   # record audio and buffer into chunks of 10
   audio = B.audio.Mic(block_duration=1)
   audio10s = B.Rebuffer(duration=10)(audio)

   # to spectrogram
   stft = B.audio.Stft()(audio)
   specshow = B.Specshow('plots/{time}.png')(spec)
   # to wavefile
   wav10s = B.audio.AudioFile('audio/{time}.wav')(audio10s)

   # Execute your pipeline
   ########################

   reip.default_graph().run()


Feel free to mix and match!

.. code-block:: python

   audio = B.audio.Mic(block_duration=1)
   # functional
   stft = B.audio.Stft()(audio)
   # chain
   spl = audio1s.to(B.audio.SPL(calibration=72.54, weighting='ZAC'))


Custom Data Processing Blocks
--------------------------------

Above we were using blocks built-in to the library. It's also extremely easy to create your own blocks that 
can process data. For example:

.. code-block:: python

   class MyOwnProcessingBlock(reip.Block):
      def init(self):
         print("I run when we start the thread")
         self.log.info("Hi!")

      def process(self, audio, meta):
         # we'll calculate audio MFCCs
         # docs: https://librosa.org/doc/latest/generated/librosa.feature.mfcc.html#librosa.feature.mfcc
         mfccs = librosa.feature.mfcc(y=audio, sr=meta['sr'], dct_type=2)
         return [mfccs], meta

      def finish(self):
         print("I run when we finish the thread")


.. toctree::
   :maxdepth: 2
   :titlesonly:
   :hidden:

   self


.. toctree::
   :maxdepth: 1
   :caption: Getting Started:

   install
   intro

.. toctree::
   :maxdepth: 1
   :caption: Examples

   audio_example
   pose_example
   recipes


.. toctree::
   :maxdepth: 1
   :caption: API

   api/blocks
   api/core
   api/stores
   api/util