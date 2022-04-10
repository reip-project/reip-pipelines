import reip
import shlex
import subprocess



class Shell(reip.Block):
    '''Run a shell command on the input data. See :py:func:`reip.util.shell.run` for 
    information about command formatting.'''
    def __init__(self, cmd, astype=str, **kw):
        self.cmd = cmd
        self.astype = astype
        super().__init__(n_inputs=None, **kw)

    def process(self, *xs, meta):
        result = reip.util.shell.run(self.cmd, *xs, **meta)
        return [self.astype(result.out.strip())], {'stderr': result.err.strip()}


class ShellProcess(reip.Block):
    '''Spawn a shell process while this block is running. There is currently
    no support for passing data to and from the process, but their outputs 
    are available via self.stdout and self.stderr.
    '''
    _proc = _pid = None
    stdout = stderr = None
    n_err_lines = 50
    def __init__(self, cmd, **kw):
        super().__init__(**kw)
        self.cmd = cmd

    def init(self):
        self._proc = subprocess.Popen(
            shlex.split(self.cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.stdout = self._proc.stdout
        self.stderr = self._proc.stderr
        self._pid = self._proc.pid
        self.log.debug('Started process {}.'.format(self._pid))

    def finish(self):
        self.log.debug('Terminating process {}...'.format(self._pid))
        self._proc.terminate()
        self.log.debug('Waiting for process {} to finish...'.format(self._pid))
        self._proc.wait()
        # if self._proc.returncode:
        #     raise RuntimeError((
        #         'Shell process exited with return code {}. \n'
        #         '  command: {} \n\n'
        #         '  error (last {} lines): \n{}').format(
        #             self._proc.returncode, self.cmd, self.n_err_lines,
        #             '\n'.join(self.stderr.getvalue().decode('utf-8').splitlines()[-self.n_err_lines:]
        #         )))
