Welcome to reip's documentation!
================================

REIP is a reconfigurable framework that allows users to quickly build data streaming pipelines for IoT-based sensor research projects.


Table of Contents
=================

.. toctree::
    :maxdepth: 2

    blocks


Concepts
========
 - **Pipeline**: An end-to-end workflow. It should have a driving block (source) that will run the downstream processing blocks. A project will typically consist of multiple pipelines that implement different pieces of functionality.
 - **Components**: A reusable combination/chain of blocks
 - **Blocks**: An atomic piece of code that consists of initialization and a transformation function with a variable number of inputs and outputs.



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
