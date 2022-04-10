REIP SDK: IoT Data Pipelines
================================

REIP is a reconfigurable framework that allows users to quickly build data streaming pipelines for IoT-based sensor research projects.

Concepts
========
 - **Pipeline**: An end-to-end workflow. It should have a driving block (source) that will run the downstream processing blocks. A project will typically consist of multiple pipelines that implement different pieces of functionality.
 - **Components**: A reusable combination/chain of blocks
 - **Blocks**: An atomic piece of code that consists of initialization and a transformation function with a variable number of inputs and outputs.


.. Quickstart
.. ---------------

.. Coming soon. Documentation under development.

.. .. code-block:: bash

..    pip install reip[video]

.. .. code-block:: python

..    import reip
..    import reip.blocks as B
..    import reip.blocks.video
..    from reip.blocks.video.models import Posenet

..    # coming soon

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