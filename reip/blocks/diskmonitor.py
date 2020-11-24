'''

Delete files when the disk is full

root_dir: /data - contains audio, spl, logs
threshold: 0.95
batch_size: 1
decision:
 - {dir: logs, }



DiskMonitor('/data', [
    ('logs', batch(n=None)),
    ('spl', delete_batch(even_distributed, n=5)),
])

'''
import os
import random
import glob
import reip
import psutil


class DiskMonitor(reip.Block):
    def __init__(self, deleter, root_dir, threshold=0.95, padding=0.1, interval=60, **kw):
        self._deleter = deleter
        self._root_dir = root_dir
        self.threshold = threshold
        self.padding = padding
        self._files = []
        super().__init__(max_rate=1./interval, extra_kw=True, **kw)

    def process(self, *files, meta):
        # initial usage check
        start_usage = self.get_usage()
        if start_usage < self.threshold:
            return

        # ok so we've exceeded, delete some files
        self._files.clear()
        self.log.warning('Disk usage exceeded ({:.1%} > {:.1%}).'.format(start_usage, self.threshold))
        self._deleter(self, **self.extra_kw)
        if not self._files:  # none we're deleted ?
            return

        # send deleted files with change in usage
        usage = self.get_usage()
        self.log.info('Removed {} files. Usage at {:.1%}.'.format(len(self._files), usage))
        return [self._files], {
            'start_usage': start_usage,
            'end_usage': usage,
            'usage_delta': start_usage - usage}

    def get_usage(self):
        return reip.util.status.storage('/')

    def get_files(self, *fs):
        return glob.glob(os.path.join(self._root_dir, *fs), recursive=True)

    def delete(self, fs):
        for f in fs:
            os.remove(f)
        self._files.extend(fs)

    def delete_while_full(self, fs, chunksize=1, randomize=True):
        chunksize = chunksize or len(fs)
        if randomize:
            random.shuffle(fs)
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

    @classmethod
    def deleter(cls, *a, **kw):
        return (
            # called deco with no arguments, just the decoed function
            reip.util.partial(cls, *a, **kw)
            if len(a) == 1 and not kw and callable(a[0]) else
            # called with misc arguments, return a function that will create
            # a partial for catching the function
            reip.util.create_partial(cls, *a, **kw)
        )




@DiskMonitor.deleter
def sonyc_deleter(block, chunksize=5):
    chunksize = chunksize or 20
    # delete all logs first
    block.delete(block.get_files('logs'))
    # first goes audio
    if block.delete_while_full(block.get_files('audio')[1::2], chunksize):
        return
    # if that's all gone, do ml
    if block.delete_while_full(block.get_files('ml')[1::2], chunksize):
        return
    # and if we have to, do spl
    if block.delete_while_full(block.get_files('spl')[1::2], chunksize):
        return
