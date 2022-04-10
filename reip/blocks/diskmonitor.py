'''

.. Delete files when the disk is full
.. 
.. root_dir: /data - contains audio, spl, logs
.. threshold: 0.95
.. batch_size: 1
.. decision:
..  - {dir: logs, }
.. 
.. 
.. 
.. DiskMonitor('/data', [
..     ('logs', batch(n=None)),
..     ('spl', delete_batch(even_distributed, n=5)),
.. ])

'''
import os
import random
import glob
import reip


class DiskMonitor(reip.Block):
    '''Monitors the disk usage in a certain directory and will selectively delete files from that directory.
    
    .. code-block:: python

        # define the file deleter

        @B.diskmonitor.Diskmonitor.deleter
        def Diskmon(block, offset=1, skip=3, chunksize=5):
            # select some subset of the files
            files = block.get_files('audio')[offset::skip]
            # randomly delete files in chunks of 5 until 
            # under the desired storage limit
            block.delete_while_full(files, chunksize)

        # instantiate the block
        with reip.Graph():
            Diskmon('/data')

        
    '''
    def __init__(self, root='/', deleter=None, threshold=0.95, padding=0.1, interval=60, **kw):
        self._deleter = deleter if callable(deleter) else self._default_deleter
        self.root = root
        self.threshold = threshold
        self.padding = padding
        self._files = []
        super().__init__(n_inputs=0, max_rate=1./interval, extra_kw=True, **kw)

    def process(self, *files, meta):
        # initial usage check
        start_usage = self.get_usage()
        if start_usage < self.threshold:
            return

        # ok so we've exceeded, delete some files
        self._files.clear()
        self.log.warning('Disk usage exceeded ({:.1%} > {:.1%}).'.format(start_usage, self.threshold))
        self._deleter(self, **self.extra_kw)

        # send deleted files with change in usage
        usage = self.get_usage()
        self.log.info('Removed {} files. Usage at {:.1%}.'.format(len(self._files), usage))
        return [self._files], {
            'start_usage': start_usage,
            'end_usage': usage,
            'usage_delta': start_usage - usage}

    def get_usage(self):
        return reip.util.status.storage(self.root, literal_keys=True)[self.root] / 100.

    def get_files(self, *fs):
        return [
            f #for root in self._root_dirs
            for f in glob.glob(os.path.join(self.root, *fs), recursive=True)
        ]

    def delete_while_full(self, fs, chunksize=1, method='random'):
        chunksize = chunksize or len(fs)
        if method == 'random':
            random.shuffle(fs)
        elif method == 'newest':
            fs = fs[::-1]
        elif method == 'oldest':
            pass
        i = -chunksize
        for usage, i in zip(self.while_full(), range(0, len(fs), chunksize)):
            self.delete(fs[i:i+chunksize])
        return i + chunksize < len(fs)

    def while_full(self, threshold=None):
        threshold = threshold if threshold is not None else (self.threshold - self.padding)
        while True:
            usage = self.get_usage()
            if usage < threshold:
                break
            yield usage

    def delete(self, fs):
        fs = reip.util.as_list(fs)
        for f in fs:
            os.remove(f)
        self._files.extend(fs)

    @classmethod
    def deleter(cls, *a, **kw):
        return (
            # called deco with no arguments, just the decoed function
            reip.util.partial(cls, *a[1:], deleter=a[0], **kw)
            if a and callable(a[0]) else
            # called with misc arguments, return a function that will create
            # a partial for catching the function
            reip.util.create_partial(cls, *a, **kw)
        )

    @staticmethod
    def _default_deleter(block):
        return block.delete_while_full(block.get_files())




# @DiskMonitor.deleter
# def SonycDiskMonitor(block, chunksize=5, skip=2, offset=1):
#     block.delete(block.get_files('logs'))  # delete all logs first
#     return (
#         block.delete_while_full(block.get_files('audio')[offset::skip], chunksize) or
#         block.delete_while_full(block.get_files('ml')[offset::skip], chunksize) or
#         block.delete_while_full(block.get_files('spl')[offset::skip], chunksize))
