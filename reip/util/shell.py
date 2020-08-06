import subprocess
import shlex
import collections

ShellResult = collections.namedtuple('ShellResult', 'out err')


def run(*cmd, **kw):
    args = {
        k: shell_args(**v) if isinstance(v, dict) else v
        for k, v in kw.items() if v is not None
    }
    r = subprocess.run(
        shlex.split(' '.join(cmd).format(**args)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return ShellResult(r.stdout.decode('utf-8'), r.stderr.decode('utf-8'))

def shell_args(**kw):
    return ' '.join(
        '{}{} {}'.format(
            '--' if len(k) > 1 else '-',
            k, '' if v is True else v).strip()
        for k, v in kw.items() if v)
