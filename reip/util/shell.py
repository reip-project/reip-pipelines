import re
import subprocess
import shlex
import collections
import reip

ShellResult = collections.namedtuple('ShellResult', 'out err rc cmd')


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
    cmd = build(cmd, *a, **kw)
    r = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, shell=True)

    return ShellResult(r.stdout.decode('utf-8'), r.stderr.decode('utf-8'), r.returncode, cmd)


def build(cmd, *a, **kw):
    return cmd.format(
        *(ShellArg(x) for x in a),
        **{k: ShellArg(v) for k, v in kw.items()})


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
                for k, v in self.value.items()
                if v is not None and v is not False
            )
        return shlex.quote(str(self.value)) if quote else str(self.value)

    def __repr__(self):
        return self._format(quote=False)

    def __str__(self):
        return self._format(quote=True)


# Misc Commands

def shmatch(cmd, out=None, err=None, rc=None):
    '''
    >>> shmatch('piwatcher status', 'OK')
    >>> shmatch('ifconfig wlan0', 'inet [.\d]+')
    >>> shmatch('docker logs blah --tail 100', err='Error')
    >>> shmatch('ls')  # true
    >>> shmatch('ls', 'README')  # true
    >>> shmatch('ls 1>&2', 'README')  # false
    >>> shmatch('ls 1>&2', err='README')  # true
    >>> shmatch('true')  # true
    >>> shmatch('true', rc=1)  # false
    >>> shmatch('false')  # false
    >>> shmatch('false', rc=1)  # true

    '''
    result = run(cmd)
    if out is None and err is None and rc is None:
        rc = 0
    return (
        (rc is None or result.rc == rc) and
        (out is None or doesmatch(result[0], out)) and
        (err is None or doesmatch(result[1], err)) or False)

def doesmatch(txt, pat=None):
    if pat is None:
        return False
    if isinstance(pat, list):
        return any(re.search(p, txt) for p in pat)
    if isinstance(pat, dict):
        return next(k for k, p in pat.items() if re.search(p, txt))
    return bool(re.search(pat, txt))  # TODO: maybe return match(es)?


def git(*cmd, root=None):
    '''Run a git command in the sonycnode repository.'''
    return run('git', dict(C=root), *cmd).out.strip()

LSUSB_FMT = (
    r'Bus\s+(?P<bus>\d+)\s+Device\s+(?P<device>\d+).+ID\s(?P<id>\w+:\w+)\s(?P<name>.+)\s*$')
def lsusb():
    res = run('lsusb')
    return [] if res.err else [
        dict(d, dev='/dev/bus/usb/{}/{}'.format(d['bus'], d['device']))
        for d in (reip.util.matchmany(l, LSUSB_FMT) for l in res.out.splitlines())
    ]


def default_routes(first=True):
    res = run('route')
    routes = [x.split()[-1] for x in res.out.splitlines() if x.startswith('default')]
    return routes and routes[0] or None if first else routes
