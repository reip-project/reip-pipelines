import os
import shlex
import hashlib
import psutil
import subprocess


class BackgroundServer:
    '''Sometimes a script needs some server running in the background.

    For example, Plasma needs to start a Plasma Store server process,
    but you only need one. Instead of requiring a user to manually do this,
    perhaps we can handle this automatically. Ideally, if a user has started
    their own server process, this should be able to identify and use the
    existing process.

    This will:
     - on spawn:
         - check if a server is already running.
         - if not, create the server
         - touch a file to let other processes know you're still using the server
     - on join:
         - remove the touched file
         - check if any other processes are still using the server.
         - if not, send SIGTERM to the server

    Example:
    >>> server = ServerProcess(
    ...     'plasma_store -s $TMPDIR/plasma -m 1000000000',
    ...     'plasma-store')

    >>> with server:
    ...     pa.put(data)


    '''
    SIGNAL = 15
    _server_pid = None
    def __init__(self, command, pattern=None):
        self.command = command
        self.pattern = pattern

        # tracking which processes are connected using a file in a directory.
        cmd_id = hashlib.md5(command.encode('utf-8')).hexdigest()[:9]
        self._pid_dir = os.path.join(
            os.getenv('TMPDIR', '/tmp'),
            f'background_server_proc_{cmd_id}')

        # this process+instance's file. this means that you can have multiple
        # instances in a certain process and it won't conflict.
        self._pid_file = os.path.join(
            self._pid_dir, f'{str(id(self))}__{os.getpid()}')

        # make sure the server pid collection dir exists.
        os.makedirs(self._pid_dir, exist_ok=True)

    @property
    def is_alive(self):
        '''Check if the server process is alive.'''
        return (
            self._server_pid in (p.pid for p in psutil.process_iter())
            if self._server_pid else self.search_process() is not None)

    @property
    def clients(self):
        '''List other clients.'''
        return os.listdir(self._pid_dir)

    def spawn(self):
        # check if a process already exists
        # if not, start a process
        p = self.search_process()
        if p is None:
            p = subprocess.Popen(self.command)
        # store the process id
        self._server_pid = p.pid
        # create the file
        with open(self._pid_file, 'a'):
            os.utime(self._pid_file)

    def join(self):
        # remove our pid file and see who else is connected
        os.remove(self._pid_file)
        pids = {f.split('__')[-1] for f in self.clients}

        # Check if all processes are dead. if yes, kill server
        alive_pids = {p.pid for p in psutil.process_iter()} & pids
        if not alive_pids:
            os.kill(self._server_pid, self.SIGNAL)

    def search_process(self):
        '''Match a process based on either the process name or the command string.'''
        return next((
            p for p in psutil.process_iter()
            if (
                # check for a substring in the process name
                self.pattern in p.name() if self.pattern else
                # if no substring was provided, then compare the commands
                shlex.split(self.command) == p.cmdline()
            )), None)

    def __enter__(self):
        self.spawn()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.join()
