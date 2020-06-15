import time

import ray
import readi
import confuse
# from sonycnode.pipeline.blocks import Block
from sonycnode.utils import misc


ray.init()

class Block:
    def __init__(self, block, then=None):
        pass

@ray.remote
class Message:
    name = 'message'
    def __init__(self, message='hello! {}'):
        self.message = message

    def __call__(self, timestamp=None, **kw):
        return self.message.format(timestamp)


class BlockCollection(readi.Collection):
    def add_context(self, vars):
        pass

    def as_block(self, block):
        return Block(block)


def load_config():
    config = confuse.Configuration()
    collection = BlockCollection()
    collection.add_context(config['vars'].get())
    collection.register_many(config['components'].get())
    return config, collection

if __name__ == '__main__':
    config, collection = load_config()
    pipelines = {
        k: collection.as_block(pipeline)
        for k, pipeline in config['pipelines'].get().items()
    }
