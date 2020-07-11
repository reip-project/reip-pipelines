import time
import numpy as np
import ray
from ..utils import block as util
import wrappingpaper as wp



@ray.remote
class Block:
    '''

    Single input, multiple outputs

    c1 = b1 | b2 | b3
    c2 = c1 | (b4, b5 | b6)

    c1 = chain(b1, b2, b3)

    c2 = chain(
        chain(b1, b2, b3),
        tee(b4, chain(b5, b6))
    )



    d1 = a1 | c1
    d2 = a2 | c1

    '''
    name = None
    output_id = data_id = meta_id = None

    def __init__(self, name=None, _chain_=None, **kw):
        self.kw = kw
        self.name = self.name or name or self.__class__.__name__

    def __or__(self, other):
        return self.outputs_to(other)

    def outputs_to(self, blocks):
        return Chain(self, blocks)

    def run(self, X=None, meta=None):
        # run this block
        self.data_id, self.meta_id = self.output_id = self._run.remote(X, meta)
        return self.data_id, self.meta_id

    def transform(self, X, meta):
        return X, meta

    def _run(self, X=None, meta=None):
        t0 = time.time()
        try:
            ret = self.transform(X, meta)
            X, meta = (
                ret if isinstance(ret, tuple) else
                (X, ret) if isinstance(ret, dict) else
                (ret, meta))

            if X is not None:
                X = np.asarray(X)
            if meta is None:
                meta = {}

            meta['empty_output'] = X is None
            meta['shape'] = X.shape if X is not None else None
        except Exception as e:
            meta['error'] = {'type': type(e), 'message': str(e)}
            raise e
        finally:
            meta['runtime'] = time.time() - t0

        return X, meta



class Chain(list):
    def __init__(self, *blocks):
        super().__init__(as_block(b) for b in blocks)

    def append(self, block):
        super().append(as_block(block))
        return self

    def extend(self, blocks):
        super().extend(as_block(b) for b in blocks)
        return self

    def outputs_to(self, block):
        self.append(block)
        return self

    def run(self, X, meta):
        for b in self:
            X, meta = b.run(X, meta)
        return X, meta


class Branch(Chain):
    def run(self, X, meta):
        return [b.run(X, meta) for b in self]



def as_block(block):
    if isinstance(block, Block):
        return block
    if isinstance(block, tuple):
        return Tee(*block)
    if callable(block):
        return LambdaBlock(block)
    # OP
    return block




# class Block:
#     '''
#
#     Schema:
#         block: the block id (includes component names)
#         name: the block config alias
#         # modify input
#         inputs:
#           some_input_key: :-1, :, :, ::-1 # numpy slice
#           last:
#             from: another_key
#             slice: -1
#         # modify output
#         outputs:
#           some_output_key: :-1, :, :, ::-1 # numpy slice
#         # output next steps
#         then:
#           - a block
#           - another block to output to
#
#     '''
#     block_key = None
#     buffer = None
#     def __init__(self, block, name=None, inputs=None, outputs=None, then=None, input_block=None, **kw):
#         # block meta data
#         self.block_key = block or self.block_key
#         self.name = name or self.name or self.__class__.__name__.lower()
#         # block data handling
#         self.input_block = input_block
#         self.to_inputs = util.make_glue(inputs)
#         self.to_outputs = util.make_glue(outputs)
#         self.output_nodes = util.tee_blocks(then, input_block=self)
#         # convert to remote function
#         def _run(inp):
#             return self.to_outputs(self.transform(**self.to_inputs(inp)))
#         self._run = ray.remote(_run)
#
#     # def __call__(self, inp):
#     #
#     #     self.run(inp)
#
#     def run(self, inp):
#         '''Run the block on an input.'''
#         return self.send_output(**self._run.remote(inp))
#
#
#
#     def transform(self, x):
#         '''Transform the block input to the desired output.'''
#         return x
#
#     def send_output(self, **out):
#         '''Send output to downstream blocks.'''
#         return [b(out) for b in self.output_nodes]
#
#     def root(self):
#         '''Get the first block in the chain.'''
#         inblock = nextblock = self
#         while nextblock:
#             inblock, nextblock = nextblock, nextblock.input_block
#         return inblock
#
#
#
# class block:
#     def __init__(self, **kw):
#         self.kw = kw
#         self._outputs = []
#
#
#     #########################
#     # Pipeline Building
#     #########################
#
#     # def add_inputs(self, *other): # return value ??
#     #     for x in other:
#     #         if isinstance(x, (tuple, list)):
#     #             return self.add_inputs(*x)
#     #         if isinstance(x, block):
#     #             x.add_outputs(self)
#     #     return self
#
#     def add_outputs(self, *other): # return value ??
#         for x in other:
#             if isinstance(x, (tuple, list)):
#                 return self.add_outputs(*x)
#             if isinstance(x, block):
#                 self._outputs.append(x)
#         return self
#
#     def update(self, *a, **kw):
#         self.kw.update(*a, **kw)
#
#     def __or__(self, other):
#         return self.add_outputs(other)
#
#     # def __ror__(self, other):
#     #     return self.add_inputs(other)
