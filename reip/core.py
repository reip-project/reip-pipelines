from . import blocks
import readi
import confuse

components.register_subclasses(blocks.Block)

class Config(confuse.Configuration):
    def __init__(self, appname='pipes', *a, **kw):
        super().__init__(appname, *a, **kw)

        # parse variables
        self.global_vars = self['vars'].get() or {}

        # parse components
        for name, cfg in (self['components'].get() or {}).items():
            components.register_variant(cfg['block'], name, **kw)

        # parse pipelines
        self.pipelines = confuse.AttrDict()
        for name, cfg in (self['pipelines'].get() or {}).items():
            self.pipelines[name] = self.get_block(cfg)

    def get_block(self, block, **kw):
        return components.getone(block, **kw)

    def run(self, *names):
        pass
