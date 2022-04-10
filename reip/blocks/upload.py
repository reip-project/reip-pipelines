import os
import sys
import time
import json
import numpy as np
from random import choice
import requests
import reip

# import os
# import time
import glob
import traceback

ALPHABETICALLY = lambda f: f.split('/')[-1]

def get_upload_files(*patterns, interval=12, empty_interval=1, sort=ALPHABETICALLY, min_mtime=3):
    '''Infinitely return files from a directory, sorted by date.
    '''
    while True:
        try:
            # get file statistics
            files = sorted((
                f for pattern in patterns
                for f in glob.iglob(pattern)
            ), key=sort, reverse=True)

            ti = time.time()
            i = 0
            while i < len(files):
                # file list expires after certain time
                if time.time() - ti > (interval if files else empty_interval):
                    break

                fname = files[i]
                # file is too young
                if min_mtime and not check_mtime(fname, min_mtime):
                    continue
                # good to go, next
                yield fname
                i += 1
        except Exception:  # some unexpected exception - assume it's a weird thing and continue on
            traceback.print_exc()

def check_mtime(fname, min_mtime):
    if min_mtime:
        try:
            mtime = os.path.getmtime(fname)
            if time.time() - mtime >= min_mtime:
                return False
        except FileNotFoundError:  # file got deleted by something, just pop and ignore
            return False
    return True



def checkfile(f):
    return f if f and os.path.isfile(f) else None


class UploadError(requests.exceptions.RequestException):
    pass


class BaseUpload(reip.Block):
    def __init__(self, endpoint, servers=None, method='post', data=None,
                 cacert=None, client_cert=None,
                 client_key=None, client_pass=None, crlfile=None,
                 timeout=60, verify=True, n_tries=5, retry_sleep=15,
                 sess=None, fake=False, **kw):
        """Data Uploader.

        Args:
            cacert (str, optional): path for the CA certificate
            client_cert (str, optional): path for client's SSL certificate
            client_key (str, optional): path for client's SSL key
            client_pass (str, optional): Password for client's SSL cert
            crlfile (str, optional): Certificate Revocation List file for checking
                if the certificate has been revoked by CA
            timeout (int): seconds to wait before timing out
        """
        self.endpoint = endpoint
        self.servers = reip.util.as_list(servers)
        self.method = method
        self.data = data
        self.verify = verify
        self.n_tries = n_tries
        self.retry_sleep = retry_sleep
        self.timeout = timeout
        self.cacert = checkfile(cacert)
        self.client_cert = checkfile(client_cert)
        self.client_key = checkfile(client_key)
        self.client_pass = client_pass or None
        self.crlfile = checkfile(crlfile)
        self.fake = fake
        self._given_sess = sess
        super().__init__(**kw)

    sess = None
    def init(self):
        self.sess = self._given_sess or requests.Session()
        self.sess.protocol = 'http'
        if self.verify:
            self.sess.protocol = 'https'
            self.sess.verify = self.cacert or True
            if self.client_cert and self.client_key:
                self.sess.cert = (self.client_cert, self.client_key)

    def process(self, *files, meta):
        pass

    def finish(self):
        self.sess = None

    def get_url(self):
        # construct url
        return '{}://{}{}'.format(
            self.sess.protocol, choice(self.servers),
            self.endpoint) if self.servers else self.endpoint

    def request(self, **kw):
        # setup
        url = self.get_url()
        datastr = self.data_str(**kw)

        if self.fake:
            return requests.Response(url), 0, 0
        #print('request', kw)
        # retry request until it succeeds
        for i in reip.util.iters.loop():
            try:
                response = self.sess.request(self.method, url, **kw, timeout=self.timeout)
                # check for non-200 error code
                if not response.ok:
                    raise UploadError('Error when uploading {} to {}.\n{}'.format(
                        datastr, url, response.text))
            except requests.exceptions.RequestException as e:
                self.log.error(reip.util.excline(e))
                # exit if we've failed too many times
                if i >= self.n_tries-1:
                    e.response = response
                    self.on_failure(response, url, **kw)
                    raise e

                time.sleep(self.retry_sleep)
            else:
                # return response info
                secs = response.elapsed.total_seconds()
                speed = self.calc_size(**kw) / secs / 1024.0
                self.log.debug('{} uploaded to {} at {:.1f} Kb/s in {:.1f}s'.format(
                    datastr, url, speed, secs))

                self.on_success(response, url, **kw)
                return response, secs, speed

    def calc_size(self, **kw):
        return os.path.getsize(kw)

    def data_str(self, **kw):
        return ''

    def on_success(self, resp, url, **kw):
        pass

    def on_failure(self, resp, url, **kw):
        pass


class _AbstractUploadFile(BaseUpload):
    def process(self, files, meta=None, data=None):
        try:
            response, secs, speed = self.request(
                files=self.as_file_dict(files),
                data=data or reip.util.resolve_call(self.data, files, meta=meta))
            return [response], {'upload_time': secs, 'upload_kbs': speed, 'status_code': response.status_code}
        except Exception as e:
            return

    def as_file_dict(self, files):
        fileobjs = {name: self.open_file(fname) for name, fname in files.items()}
        return {k: (os.path.basename(fn), f) for k, (fn, f) in fileobjs.items()}

    def data_str(self, files, **kw):
        return ', '.join(os.path.join(k, fn) for k, (fn, f) in files.items())

    def open_file(self, fname):
        return fname, open(fname, 'rb')

    def calc_size(self, files, **kw):
        return sum(os.path.getsize(f) for f in files.values())


class UploadFile(_AbstractUploadFile):
    def __init__(self, *a, names=None, remove_on_success=True, **kw):
        self.names = reip.util.as_list(names or ())
        self.remove_on_success = remove_on_success
        super().__init__(*a, **kw)

    def process(self, *fs, meta=None):
        return super().process({
                reip.util.resolve_call(self.names[i], fname)
                if i < len(self.names) else
                os.path.basename(os.path.dirname(fname))
                or os.path.basename(fname): fname
                for i, fname in enumerate(fs)
            }, data=reip.util.resolve_call(self.data, *fs, meta=meta))

    def on_success(self, resp, url, files, **kw):
        if self.remove_on_success: # delete file
            for f in files.values():
                os.remove(f)



class UploadJSONAsFile(_AbstractUploadFile):
    FILENAME = 'status.json'
    def process(self, *data, meta=None):
        status = {k: v for d in data for k, v in d.items()}
        data = reip.util.resolve_call(self.data, status, meta=meta)
        return super().process({'file': status}, meta=meta, data=data)

    def open_file(self, status):
        return self.FILENAME, json.dumps(status, cls=NumpyEncoder)

    def calc_size(self, files):
        return sum(sys.getsizeof(x) for x in files.values())




class UploadJSON(BaseUpload):
    def process(self, *data, meta=None):
        status = {k: v for d in data for k, v in d.items()}
        try:
            data = reip.util.resolve_call(self.data, status, meta=meta) or {}
            response, secs, speed = self.request(json=dict(data, **status))
            return [response], {'upload_time': secs, 'upload_kbs': speed, 'status_code': response.status_code}
        except Exception as e:
            return

    def calc_size(self, data=None, json=None, **kw):
        return sys.getsizeof(data)








class UploadFilesFromDirectory(UploadFile):
    def __init__(self, endpoint, *patterns, n_inputs=0, **kw):
        self.patterns = patterns
        super().__init__(endpoint, n_inputs=n_inputs, **kw)

    def init(self):
        self.iter_files = get_upload_files(*self.patterns)

    def process(self, meta):
        fname = next(self.iter_files)
        return super().process(fname, meta=meta)





class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
