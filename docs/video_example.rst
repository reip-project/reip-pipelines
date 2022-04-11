
Video Demos
------------------

For all demos you can use this helper function that will run the graph and 
stream video to opencv in the main thread. Working in the main thread is important 
for UI things like opencv and matplotlib.

.. code-block:: python

    import cv2
    from contextlib import closing

    def run_with_video(g, stream):
        with g.run_scope():
            with closing(B.video.stream_imshow(stream, 'blah')) as it:
                for _ in reip.util.iters.resample_iter(it, 5):
                    print(g.status())

If you'd rather work with cv2 directly, you can do something like this:

.. code-block:: python

    def run_with_video_alt(graph, stream, name='video-stream'):
        with graph.run_scope():
            try:
                cv2.namedWindow(name)
                for [image], meta in stream:
                    cv2.imshow(name, image)
                    if cv2.waitKey(25) & 0xFF == ord('q'):
                        return
            finally:
                cv2.destroyWindow(name)



Simple Camera
===================

.. code-block:: python

    import reip
    import reip.blocks as B
    import reip.blocks.video

    camera = 0  # your camera's index'

    with reip.Graph() as g:
        cam = B.video.Video(camera)#.to(B.Debug('video'))
    stream = cam.output_stream(strategy='latest')
    run_with_video(g, stream)



Object Detection
===================

.. code-block:: python

    from reip.blocks.video.models.objects import Objects

    camera = 0

    with reip.Graph() as g:
        cam = B.video.Video(camera)#.to(B.Debug('video'))
        out = Objects()(cam, strategy='latest')
    stream = out[1].output_stream(strategy='latest')
    run_with_video(g, stream)

Pose Detection
===================

.. code-block:: python

    from reip.blocks.video.models.posenet import Posenet

    camera = 0

    with reip.Graph() as g:
        cam = B.video.Video(camera)
        out = Posenet(log_level='debug')(cam, strategy='latest')
    stream = out[1].output_stream(strategy='latest')
    run_with_video(g, stream)

Image Segmentation
===================

.. code-block:: python

    from reip.blocks.video.models.segmentation import Segment

    camera = 0

    with reip.Graph() as g:
        cam = B.video.Video(camera)
        out = Segment(log_level='debug')(cam, strategy='latest')
    stream = out[1].output_stream(strategy='latest')
    run_with_video(g, stream)

Optical Flow
===================

.. code-block:: python

    camera = 0

    with reip.Graph() as g:
        cam = B.video.Video(camera)
        flow = B.video.effects.OpticalFlow()(cam, strategy='latest')
    stream = flow[1].output_stream(strategy='latest')
    run_with_video(g, stream) 

.. .. code-block:: python

..     import reip
..     import reip.blocks as B
..     import reip.blocks.video
..     import reip.blocks.ml


..     with reip.Graph() as g:
..         B.audio.Mic()

..         B.ml.Tflite()

..         # SPL
..         # ML
..         # 