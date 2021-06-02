import functools
import base_app
from waggle import plugin

plugin.init()


class PublishQueue:
    def __init__(self, key, max_len=None):
        self.key = key

    def empty(self):
        return True

    def full(self):
        return False

    def put(self, x):
        plugin.publish(self.key, x)

    def get(self, **kw):
        return


class FileQueue(PublishQueue):
    def put(self, x):
        plugin.upload_file(x)

    def get(self, **kw):
        return


class Block(base_app.Block):
    def __init__(self, *a, publish=False, **kw):
        super().__init__(*a, **kw)
        if publish == 'file':
            self.output_customers.append(FileQueue())
        elif publish:
            if publish is True:
                publish = self.name
            self.output_customers.append(PublishQueue(publish))


class PublishBlock(Block):
    def __init__(self, key):
        self.key = key

    def process(self, *inputs):
        result = super().process(*inputs)
        if result is None:
            return
        [x, meta] = base_app.convert_inputs(result)
        plugin.publish(self.key, x)


class FileBlock(Block):
    def process(self, x):
        result = super().process(*inputs)
        if result is None:
            return
        [x, meta] = base_app.convert_inputs(result)
        plugin.upload_file(x)


B = base_app.example(Block)
test = functools.partial(base_app.test, B=B)

if __name__ == '__main__':
    import fire
    fire.Fire(test)