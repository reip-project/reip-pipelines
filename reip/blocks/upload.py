import os
import sys
import json
from random import choice
import requests
import reip


def checkfile(f):
    return f if f and os.path.isfile(f) else None


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

    def process(self, files, meta=None, post_data=None):
        # send request
        url = self.get_url()
        fileobjs = {
            name: self.open_file(fname)
            for name, fname in files.items()
        }
        names = ', '.join(fn for fn, f in fileobjs.values())#files.keys())
        self.log.debug("Uploading: {} to {}".format(names, url))
        response = self.sess.post(
            url, files=fileobjs,
            data=post_data or reip.util.resolve_call(self.data, files, meta=meta),
            timeout=self.timeout)

        # return response info
        secs = response.elapsed.total_seconds()
        output = response.text
        speed = self.calc_size(files) / secs / 1024.0
        # handle output
        if response.ok:
            self.log.debug('{} uploaded at {:.1f} Kb/s in {:.1f}s'.format(
                names, speed, secs))
            self.on_success(files, output)
        else:
            self.log.error('Error when uploading to {}.\n{}'.format(url, output))
            self.on_failure(files, output)
        return [output], {'upload_time': secs, 'upload_kbs': speed}

    def open_file(self, fname):
        return os.path.basename(fname), open(fname, 'rb')

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
        return self.FILENAME, json.dumps(status)

    def calc_size(self, files):
        return sum(sys.getsizeof(x) for x in files.values())

        # # return response info
        # secs = response.elapsed.total_seconds()
        # output = response.text
        # speed = sys.getsizeof(status) / secs / 1024.0
        # # handle output
        # if response.ok:
        #     self.log.debug('{} uploaded at {:.1f} Kb/s in {:.1f}s'.format(
        #         name, speed, secs))
        # else:
        #     self.log.error('Error when uploading to {}.\n{}'.format(url, output))
        # return [output], {'upload_time': secs, 'upload_kbs': speed}
