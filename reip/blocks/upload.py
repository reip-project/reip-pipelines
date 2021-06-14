import os
import sys
import time
import json
import numpy as np
from random import choice
import requests
import reip


def checkfile(f):
    return f if f and os.path.isfile(f) else None


class UploadError(requests.exceptions.RequestException):
    response = None
    def __init__(self, message, response=None, **kw):
        super().__init__(message, **kw)
        self.response = request if self.response is None else self.response


def reword_exception(exc, message):
    exc2 = type(exc)(message)
    exc2.__dict__ = exc.__dict__
    return exc2


class BaseUpload(reip.Block):
    Session = requests.Session
    def __init__(self, endpoint, servers=None, method='post', data=None,
                 cacert=None, client_cert=None,
                 client_key=None, client_pass=None, crlfile=None,
                 timeout=20, verify=True, n_tries=5, retry_sleep=15,
                 sess=None, **kw):
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
        self._given_sess = sess
        super().__init__(**kw)

    sess = None
    def init(self):
        self.sess = self._given_sess or self.Session()
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
        url = self.get_url()
        datastr = self.data_str(**kw)
        response = self.sess.request(self.method, url, **kw, timeout=self.timeout)
        try:
            response.raise_for_status()
        except Exception as e:
            raise reword_exception(e, 'Error when uploading {} to {}. {}'.format(datastr, url, e))
        # check for non-200 error code
        if not response.ok:
            raise UploadError('Error when uploading {} to {}.\n{}'.format(
                datastr, url, response.text), response)

        # return response info
        secs = response.elapsed.total_seconds()
        speed = self.calc_size(**kw) / secs / 1024.0
        self.log.info('{} uploaded to {} at {:.1f} Kb/s in {:.1f}s'.format(
            datastr, url, speed, secs))

        self.on_success(response, url, **kw)
        return response, secs, speed

    def retry_loop(self):
        for i in reip.util.iters.loop():
            try:
                yield
            except Exception as e:
                # exit if we've failed too many times
                if not self.n_tries or i >= self.n_tries-1:
                    self.on_failure(response, url, **kw)
                    raise e
                self.log.error(reip.util.excline(e))

    def calc_size(self, **kw):
        return os.path.getsize(kw)

    def data_str(self, **kw):
        return ''

    def on_success(self, resp, url, **kw):
        pass

    def on_failure(self, resp, url, **kw):
        pass


class UploadFile(BaseUpload):
    def __init__(self, *a, names=None, remove_on_success=True, **kw):
        self.names = reip.util.as_list(names or ())
        self.remove_on_success = remove_on_success
        super().__init__(*a, **kw)


    def _process(self, *fs, meta=None):
        files = [
            (reip.util.resolve_call(self.names[i], fname)
                if i < len(self.names) else
                os.path.basename(os.path.dirname(fname))
                or os.path.basename(fname), fname)
            for i, fname in enumerate(fs)
        ]
        data = reip.util.resolve_call(self.data, files, meta=meta)

        for _ in self.retry_loop():
            response, secs, speed = self.request(files=self.as_file_dict(files), data=data)
            self.on_file_success(*fs)
            return [response], {'upload_time': secs, 'upload_kbs': speed, 'status_code': response.status_code}

    def process(self, *fs, meta=None):
        try:
            return self._process(*fs, meta=meta)
        except Exception as e:
            self.log.exception(e)
            return

    def as_file_dict(self, files):
        fileobjs = {name: self.open_file(fname) for name, fname in (files.items() if isinstance(files, dict) else files)}
        return {k: (os.path.basename(fn), f) for k, (fn, f) in fileobjs.items()}

    def data_str(self, files, **kw):
        return ', '.join(os.path.join(k, fn)+'({})'.format(reip.util.human_time(time.time()-os.path.getmtime(f.name))) for k, (fn, f) in files.items())

    def open_file(self, fname):
        return fname, open(fname, 'rb')

    def calc_size(self, files, **kw):
        return sum(os.path.getsize(f.name) if hasattr(f, 'name') else sys.getsizeof(f) for _, f in files.values())

    def on_file_success(self, *files):
        if self.remove_on_success: # delete file
            for f in files:
                os.remove(f)



class UploadJSON(BaseUpload):
    def process(self, *data, meta=None):
        try:
            merged = {k: v for d in data for k, v in d.items() if d}
            data = dict(merged, **(reip.util.resolve_call(self.data, merged, meta=meta) or {}))
            datajson = json.dumps(data, cls=NumpyEncoder)

            for _ in self.retry_loop():
                response, secs, speed = self.request(data=datajson, headers={'Content-Type': 'application/json'})
                return [response], {'upload_time': secs, 'upload_kbs': speed, 'status_code': response.status_code}
        # connection error
        except requests.exceptions.Timeout as e:
            self.log.error('Timeout when uploading JSON. {}'.format(reip.util.excline(e)))
        except Exception as e:
            self.log.exception(e)
            return

    def calc_size(self, data=None, json=None, **kw):
        return sys.getsizeof(data)




class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
