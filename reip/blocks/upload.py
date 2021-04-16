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
    pass


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
        # setup
        url = self.get_url()
        datastr = self.data_str(**kw)
        #print('request', kw)
        # retry request until it succeeds
        for i in reip.util.iters.loop():
            response = None
            try:
                response = self.sess.request(self.method, url, **kw, timeout=self.timeout)
                response.raise_for_status()
                # check for non-200 error code
                if not response.ok:
                    raise UploadError('Error when uploading {} to {}.\n{}'.format(
                        datastr, url, response.text))
            except Exception as e:
                self.log.error(reip.util.excline(e))
                # exit if we've failed too many times
                if i >= self.n_tries-1:
                    e.response = response
                    self.on_failure(response, url, **kw)
                    raise e

            else:
                # return response info
                secs = response.elapsed.total_seconds()
                speed = self.calc_size(**kw) / secs / 1024.0
                self.log.info('{} uploaded to {} at {:.1f} Kb/s in {:.1f}s'.format(
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


class UploadFile(BaseUpload):
    def __init__(self, *a, names=None, remove_on_success=True, **kw):
        self.names = reip.util.as_list(names or ())
        self.remove_on_success = remove_on_success
        super().__init__(*a, **kw)

    def process(self, *fs, meta=None):
        try:
            files = [
                (reip.util.resolve_call(self.names[i], fname)
                 if i < len(self.names) else
                 os.path.basename(os.path.dirname(fname))
                 or os.path.basename(fname), fname)
                for i, fname in enumerate(fs)
            ]

            response, secs, speed = self.request(
                files=self.as_file_dict(files),
                data=reip.util.resolve_call(self.data, files, meta=meta))
            self.on_file_success(*fs)

            return [response], {'upload_time': secs, 'upload_kbs': speed, 'status_code': response.status_code}
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


# class UploadFile(_AbstractUploadFile):
#    def __init__(self, *a, names=None, remove_on_success=True, **kw):
#         self.names = reip.util.as_list(names or ())
#         self.remove_on_success = remove_on_success
#         super().__init__(*a, **kw)
# 
#     def process(self, *fs, meta=None):
#         return super().process([
#                 (reip.util.resolve_call(self.names[i], fname)
#                  if i < len(self.names) else
#                  os.path.basename(os.path.dirname(fname))
#                  or os.path.basename(fname), fname)
#                 for i, fname in enumerate(fs)
#             ], data=reip.util.resolve_call(self.data, *fs, meta=meta))

#     def on_success(self, resp, url, files, **kw):
#         if self.remove_on_success: # delete file
#             for f in files.values():
#                 if isinstance(f, tuple):
#                     f = f[0]
#                 os.remove(f)



#class UploadJSONAsFile(_AbstractUploadFile):
#    FILENAME = 'status.json'
#    def process(self, *data, meta=None):
#        status = {k: v for d in data for k, v in d.items()}
#        data = reip.util.resolve_call(self.data, status, meta=meta)
#        return super().process({'file': status}, meta=meta, data=data)
#
#    def open_file(self, status):
#        return self.FILENAME, json.dumps(status, cls=NumpyEncoder)
#
#    def calc_size(self, files):
#        return sum(sys.getsizeof(x) for x in files.values())




class UploadJSON(BaseUpload):
    def process(self, *data, meta=None):
        status = {k: v for d in data for k, v in d.items()}
        try:
            data = dict(reip.util.resolve_call(self.data, status, meta=meta) or {}, **status)
            response, secs, speed = self.request(
                data=json.dumps(data, cls=NumpyEncoder), 
                headers={'Content-Type': 'application/json'})
            return [response], {'upload_time': secs, 'upload_kbs': speed, 'status_code': response.status_code}
        except Exception as e:
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
