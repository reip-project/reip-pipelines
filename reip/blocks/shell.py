import reip



class Shell(reip.Block):
    def __init__(self, cmd, **kw):
        self.cmd = cmd
        super().__init__(**kw)

    def process(self, meta):
        result = reip.util.shell.run(self.cmd)
        return [result.out, result.err], {}
