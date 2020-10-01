import os
import sys
import json
from random import choice
import requests
import reip


def checkfile(f):
    return f if f and os.path.isfile(f) else None


class Upload(reip.Block):
    def __init__(self,
                 endpoint,
                 data=None,
                 http_servers=None,
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
        self.http_servers = http_servers
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
            self.sess.protocol, choice(self.http_servers),
            self.endpoint) if self.http_servers else self.endpoint


class UploadFile(Upload):
    def __init__(self, *a, remove_on_success=True, **kw):
        self.remove_on_success = remove_on_success
        super().__init__(*a, **kw)

    def process(self, *files, meta=None):
        # data_dir = os.path.basename(os.path.dirname(fname))
        files = {os.path.basename(fname): fname for fname in files}

        # send request
        url = self.get_url()
        names = ', '.join(files.keys())
        self.log.info("Uploading: {} to {}".format(names, url))
        response = self.sess.post(
            url, files={
                name: (name, open(fname, 'rb'))
                for name, fname in files.items()
            }, data=self.data,
            timeout=self.timeout)

        # return response info
        secs = response.elapsed.total_seconds()
        output = response.text
        speed = sum(os.path.getsize(f) for f in files.values()) / secs / 1024.0

        if output == '0':
            self.log.info('{} uploaded at {:.1f} Kb/s in {:.1f}s'.format(
                names, speed, secs))
            if self.remove_on_success: # delete file
                for f in files.values():
                    os.remove(f)
        else:
            self.log.error(output)

        secs = response.elapsed.total_seconds()
        return [output], {'upload_time': secs, 'upload_kbs': speed}


class UploadStatus(Upload):
    def process(self, *data, meta=None):
        status = {}
        for d in data:
            status.update(d)

        url = self.get_url()
        name = 'status'
        self.log.info("Uploading: {} to {}".format(name, url))
        response = self.sess.post(
            url, files={
                'file': ('{}.json'.format(name), json.dumps(status))
            }, data=reip.util.resolve_call(self.data, *data, meta=meta),
            timeout=self.timeout)

        # return response info
        secs = response.elapsed.total_seconds()
        output = response.text
        speed = sys.getsizeof(status) / secs / 1024.0

        if output == '0':
            self.log.info('{} uploaded at {:.1f} Kb/s in {:.1f}s'.format(
                name, speed, secs))
        else:
            self.log.error(output)

        secs = response.elapsed.total_seconds()
        return [output], {'upload_time': secs, 'upload_kbs': speed}
