# from lazyimport
import requests
from .block import Block
from .. import util


class upload(Block):
    method = None
    def __init__(self, url, endpoint=None, method='get'):
        self.method = method
        self.url = url
        self.endpoint = endpoint
        self.session = requests.Session()


    def transform(self, data, meta):
        resp = self.session.request(
            self.method, self.url + self.endpoint,
            params={},
            data={},
            files={})

        return resp.json()


class get(upload):
    method = 'GET'


class post(upload):
    method = 'POST'


class delete(upload):
    method = 'DELETE'


upload.get = get
upload.post = post
upload.delete = delete
upload.file = file
