from contextlib import closing
import reip
import reip.blocks as B
import reip.blocks.video



def camera(camera=0):
    '''Simply show video from the camera.'''
    with reip.Graph() as g:
        cam = B.video.Video(camera)#.to(B.Debug('video'))
    stream = cam.output_stream(strategy='latest')

    with g.run_scope():
        with closing(B.video.stream_imshow(stream, 'blah')) as it:
            for _ in reip.util.iters.resample_iter(it, 5):
                print(g.status())


def objects(camera=0):
    '''Show video from your camera with object detections.'''
    from reip.blocks.video.models.objects import Objects

    with reip.Graph() as g:
        cam = B.video.Video(camera)
        out = Objects()(cam, strategy='latest')
    stream = out[1].output_stream(strategy='latest')

    with g.run_scope():
        with closing(B.video.stream_imshow(stream, 'blah')) as it:
            for _ in reip.util.iters.resample_iter(it, 5):
                print(g.status())


def pose(camera=0):
    '''Show video from your camera with pose detections.'''
    from reip.blocks.video.models.posenet import Posenet

    with reip.Graph() as g:
        cam = B.video.Video(camera)
        out = Posenet(log_level='debug')(cam, strategy='latest')
    stream = out[1].output_stream(strategy='latest')

    with g.run_scope():
        with closing(B.video.stream_imshow(stream, 'blah')) as it:
            for _ in reip.util.iters.resample_iter(it, 5):
                print(g.status())


def segment(camera=0):
    '''Show video from your camera with image segmentation.'''
    from reip.blocks.video.models.segmentation import Segment

    with reip.Graph() as g:
        cam = B.video.Video(camera)
        out = Segment(log_level='debug')(cam, strategy='latest')
        # out[0].to(B.Debug('seg'))
        # out[1].to(B.Debug('ims'))
    stream = out[1].output_stream(strategy='latest')

    with g.run_scope():
        with closing(B.video.stream_imshow(stream, 'blah')) as it:
            for _ in reip.util.iters.resample_iter(it, 5):
                print(g.status())


def flow(camera=0):
    '''Show video from your camera with optical flow.'''
    with reip.Graph() as g:
        cam = B.video.Video(camera)
        out = flow = B.video.effects.OpticalFlow()(cam, strategy='latest')
        # B.Debug('of')(out[0])
    stream = out[1].output_stream(strategy='latest')

    with g.run_scope():
        with closing(B.video.stream_imshow(stream, 'blah')) as it:
            for _ in reip.util.iters.resample_iter(it, 5):
                print(g.status())




if __name__ == '__main__':
    import fire
    fire.Fire()