import os
import sys
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
    def __init__(self,
                 endpoint,
                 data=None,
                 servers=None,
                 cacert=None,
                 client_cert=None,
                 client_key=None,
                 client_pass=None,
                 crlfile=None,
                 timeout=60,
                 verify=True, **kw):
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
        self.data = data
        self.servers = servers
        self.verify = verify
        self.timeout = timeout
        self.cacert = checkfile(cacert)
        self.client_cert = checkfile(client_cert)
        self.client_key = checkfile(client_key)
        self.client_pass = client_pass or None
        self.crlfile = checkfile(crlfile)
        super().__init__(**kw)

    sess = None
    def init(self):
        self.sess = requests.Session()
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


class _AbstractUploadFile(BaseUpload):
    def __init__(self, *a, n_tries=4, retry_sleep=10, **kw):
        super().__init__(*a, **kw)
        self.n_tries = n_tries or None
        self.retry_sleep = retry_sleep

    # def init(self):
    #     super().init()
    #     self.failed_uploads = []

    def process(self, files, meta=None, post_data=None):
        # prepare request
        url = self.get_url()
        fileobjs = {
            name: self.open_file(fname)
            for name, fname in files.items()
        }
        names = ', '.join(fn for fn, f in fileobjs.values())#files.keys())
        # self.log.debug("Uploading: {} to {}".format(names, url))

        to_upload = {k: (os.path.basename(fn), f) for k, (fn, f) in fileobjs.items()}
        if post_data is None:
            post_data = reip.util.resolve_call(self.data, files, meta=meta)

        # send request and possibly retry
        for _ in reip.util.iters.loop(self.n_tries):
            try:
                response = self.sess.post(url, files=to_upload, data=post_data, timeout=self.timeout)
                output = response.text

                # check for non-200 error code
                if not response.ok:
                    raise UploadError('Error when uploading {} to {}.\n{}'.format(url, names, output))
            except requests.exceptions.RequestException as e:
                self.log.error(reip.util.excline(e))
                time.sleep(self.retry_sleep)
            else:
                break
        else:
            self.on_failure(files, output)
            return [output], {'error': True, 'status_code': response.status_code}  # XXX: what to return here ?

        # return response info
        secs = response.elapsed.total_seconds()
        speed = self.calc_size(files) / secs / 1024.0

        self.log.debug('{} uploaded to {} at {:.1f} Kb/s in {:.1f}s'.format(
            names, url, speed, secs))
        self.on_success(files, output)

        return [output], {'upload_time': secs, 'upload_kbs': speed, 'status_code': response.status_code}

    def open_file(self, fname):
        return fname, open(fname, 'rb')

    def calc_size(self, files):
        return sum(os.path.getsize(f) for f in files.values())

    def on_success(self, files, output):
        pass

    def on_failure(self, files, output):
        pass


class UploadFile(_AbstractUploadFile):
    def __init__(self, *a, names=None, remove_on_success=True, **kw):
        self.names = reip.util.as_list(names or ())
        self.remove_on_success = remove_on_success
        super().__init__(*a, **kw)

    def process(self, *fs, meta=None):
        files = {
            reip.util.resolve_call(self.names[i], fname)
            if i < len(self.names) else
            os.path.basename(fname): fname
            for i, fname in enumerate(fs)}
        data = reip.util.resolve_call(self.data, *fs, meta=meta)
        return super().process(files, post_data=data, meta=meta)

    def on_success(self, files, output):
        if self.remove_on_success: # delete file
            for f in files.values():
                os.remove(f)



class UploadJSONAsFile(_AbstractUploadFile):
    FILENAME = 'status.json'
    def process(self, *data, meta=None):
        status = {}
        for d in data:
            status.update(d)
        data = reip.util.resolve_call(self.data, status, meta=meta)
        return super().process({'file': status}, post_data=data, meta=meta)

    def open_file(self, status):
        return self.FILENAME, json.dumps(status, cls=NumpyEncoder)

    def calc_size(self, files):
        return sum(sys.getsizeof(x) for x in files.values())


class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
