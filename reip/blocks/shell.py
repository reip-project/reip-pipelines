import reip



class Shell(reip.Block):
    def __init__(self, cmd, astype=str, **kw):
        self.cmd = cmd
        self.astype = astype
        super().__init__(**kw)

    def process(self, *xs, meta):
        result = reip.util.shell.run(self.cmd, posargs=xs, **meta)
        return [self.astype(result.out.strip())], {'stderr': result.err.strip()}
