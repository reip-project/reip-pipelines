import numpy as np
import ray
from ..utils import block as util
import wrappingpaper as wp


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
        '''Run the block on an input.'''
        self.run(inp)

    def run(self, inp):
        return self.send_output(**self._run.remote(inp))

    def transform(self, x):
        '''Transform the block input to the desired output.'''
        return x

    def send_output(self, **out):
        '''Send output to downstream blocks.'''
        return [b(out) for b in self.output_nodes]

    def root(self):
        '''Get the first block in the chain.'''
        inblock = nextblock = self
        while nextblock:
            inblock, nextblock = nextblock, nextblock.input_block
        return inblock



class block:
    def __init__(self, **kw):
        self.kw = kw
        self._outputs = []


    #########################
    # Pipeline Building
    #########################

    # def add_inputs(self, *other): # return value ??
    #     for x in other:
    #         if isinstance(x, (tuple, list)):
    #             return self.add_inputs(*x)
    #         if isinstance(x, block):
    #             x.add_outputs(self)
    #     return self

    def add_outputs(self, *other): # return value ??
        for x in other:
            if isinstance(x, (tuple, list)):
                return self.add_outputs(*x)
            if isinstance(x, block):
                self._outputs.append(x)
        return self

    def update(self, *a, **kw):
        self.kw.update(*a, **kw)

    def __or__(self, other):
        return self.add_outputs(other)

    # def __ror__(self, other):
    #     return self.add_inputs(other)
