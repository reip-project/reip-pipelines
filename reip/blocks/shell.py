import reip



class Shell(reip.Block):
    def __init__(self, cmd, astype=str, **kw):
        self.cmd = cmd
        self.astype = astype
        super().__init__(n_source=None, **kw)

    def process(self, *xs, meta):
        result = reip.util.shell.run(self.cmd, *xs, **meta)
        return [self.astype(result.out.strip())], {'stderr': result.err.strip()}
