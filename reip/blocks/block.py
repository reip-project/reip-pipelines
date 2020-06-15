import numpy as np
import ray
from ..utils import block as util


class Block:
    '''

    Schema:
        block: the block id (includes component names)
        name: the block config alias
        # modify input
        inputs:
          some_input_key: :-1, :, :, ::-1 # numpy slice
          last:
            from: another_key
            slice: -1
        # modify output
        outputs:
          some_output_key: :-1, :, :, ::-1 # numpy slice
        # output next steps
        then:
          - a block
          - another block to output to

    '''
    block_key = None
    buffer = None
    def __init__(self, block, name=None, inputs=None, outputs=None, then=None, input_block=None, **kw):
        # block meta data
        self.block_key = block or self.block_key
        self.name = name or self.name or self.__class__.__name__.lower()
        # block data handling
        self.input_block = input_block
        self.to_inputs = util.make_glue(inputs)
        self.to_outputs = util.make_glue(outputs)
        self.output_nodes = util.tee_blocks(then, input_block=self)
        # convert to remote function
        def _run(inp):
            return self.to_outputs(self.transform(**self.to_inputs(inp)))
        self._run = ray.remote(_run)

    def __call__(self, inp):
        self.run(inp)

    def run(self, inp):
        return self.send_output(**self._run.remote(inp))

    def transform(self, x):
        return x

    def send_output(self, out):
        return [b(out) for b in self.output_nodes]

    def root(self):
        inblock = nextblock = self
        while nextblock:
            inblock, nextblock = nextblock, nextblock.input_block
        return inblock

    def open(self):
        return self

    def close(self):
        return self

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
