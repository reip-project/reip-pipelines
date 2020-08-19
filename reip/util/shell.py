import subprocess
import shlex
import collections

ShellResult = collections.namedtuple('ShellResult', 'out err cmd')


def run(cmd, *a, **kw):
    '''Run a shell command. Dictionary arguments passed will be converted to
    bash flags. e.g.: dict(x=5, y=True, z=None) -> '-x 5 -y'

    Arguments:
        cmd (str): the command to run. By default, arguments will be quoted.
            To pass a value without quoting, use the format pattern `{!r}`.
        *args, **kwargs: arguments to format command with.
            If any arg is None, it will insert an empty string.
            If any argument is a dict, it will attempt to format it as bash flags.
             - If the key is a single character, only a single preceding dash
               will be used.
             - if the value is True, then it will output like a boolean flag.
               e.g.: dict(asdf=True) => --asdf
             - if the value is None or False, then it will be omitted.
             - otherwise, it will be cast to a string.

    Examples:
    >>> shell.run('echo 10')  # echo 10
    # ('10\n', '')
    >>> shell.run('echo {}', '10 && echo 15')  # echo '10 && echo 15'
    # ('10 && echo 15\n', '')
    >>> shell.run('echo {!r}', '10 && echo 15')  # echo 10 && echo 15
    # ('10\n15\n', '')
    >>> shell.run('echo {} {b} {a}', 10, a=11, b=15)  # echo 10 15 11
    # ('10 15 11\n', '')
    >>> iface = None  # wlan0
    ... shell.run('ping {} 8.8.8.8', dict(I=iface, c=3))  # ping -c 3 8.8.8.8
    # ('PING 8.8.8.8 ...', '')
    # NOTE: notice how because -I is None, it gets filtered out.

    '''
    cmd = cmd.format(
        *(ShellArg(x) for x in a),
        **{k: ShellArg(v) for k, v in kw.items()})
    r = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, shell=True)

    return ShellResult(r.stdout.decode('utf-8'), r.stderr.decode('utf-8'), cmd)


class ShellArg:
    '''Formats a user-specified argument as a bash argument.

    If value is a dict, it will be constructed as a series of flags. Otherwise
    it will just convert to string and potentially quote the value.
    '''
    def __init__(self, value):
        self.value = value

    def _format(self, quote=False):
        if self.value is None:
            return ''
        if isinstance(self.value, dict):
            return ' '.join(
                '{}{} {}'.format(
                    '--' if len(k) > 1 else '-', k,
                    '' if v is True else shlex.quote(str(v)) if quote else v
                ).strip()
                for k, v in self.value.items() if v is not None and v is not False)
        return shlex.quote(str(self.value)) if quote else str(self.value)

    def __repr__(self):
        return self._format(quote=False)

    def __str__(self):
        return self._format(quote=True)
