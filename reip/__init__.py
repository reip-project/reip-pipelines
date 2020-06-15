import readi
components = readi.Collection('pipes_blocks')
from . import blocks


def make_pipeline(*blocks):
    def inner(**kw):
        pass
    return inner

def eval_blocks(blocks, inputs=None):
    outputs = []
    for block in blocks:
        if isinstance(block, (list, tuple)):
            inputs = eval_blocks(blocks, inputs)
        else:
            inputs = block(inputs)
    return inputs

def get_block(block, then=None, _squeeze=False, **kw):
    if isinstance(block, dict):
        return get_block(**kw, **block)
    if isinstance(block, (list, tuple)):
        return [get_block(b, then=then, **kw) for b in block]

    b = block if isinstance(block, block.Block) else components.getone(block, **kw)
    bs = tee_blocks(then)
    return [b, bs] if bs else [b]


def get_tee_blocks(bls, **kw):
    '''
    block1:
        then:
            block2:
                then:
                    - block3:
                    - block4:
                        then: block5:
                    - block6:

    [block1, block2, [[block3], [block4, block5], [block]]]
    '''
    return apply_multi(get_block, bls, **kw, _squeeze=True)

def apply_multi(func, objs, multitype=(list, dict), **kw):
    if objs is None:
        return
    is_single = not isinstance(objs, multitype)
    objs = [objs] if is_single else objs
    objs = [func(x, **kw) for x in objs]
    return objs[0] if is_single else objs


if __name__ == '__main__':
    components = {
        'data_dump': lambda name, status: [
            blocks.State(inputs=status),
            [
                blocks.CSV(
                    filename='{{ tmp_root }}/' + name + '/{{ root.time }}.csv',
                    then=blocks.Tar(filename='{{ data_root }}/' + name + '/{{ root.time }}.tar.gz')),

            ]
        ]
    }

    audio_pipe = make_pipeline([
        blocks.AudioSource(then=[
            blocks.SPL(then=components['data_dump'](
                name='spl', status={'leq': 'leq[-1]', 'laeq': 'laeq[-1]'})),
            blocks.Tflite(then=components['data_dump'](
                name='ml', status=dict(
                    embedding='embedding[-1]',
                    classification='classification[-1]'))),
        ]),

    ])

    upload_pipe = make_pipeline([
        blocks.Interval(),
        [
            blocks.UploadStatus(),
            blocks.UploadData(),
        ]
    ])

    audio_pipe()
    upload_pipe()
