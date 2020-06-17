'''
File Encryption
===========

Two Step Encryption
-------------------
.. autosummary::
    :toctree: generated/

    TwoStepEncryptFile
    TwoStepDecryptFile

'''

import os
import io
import base64
import tarfile
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

from .block import Block

class TwoStepBase:
    def __init__(self, *a, rsa_key, **kw):
        super().__init__(*a, **kw)
        self.rsa_key = rsa_key

    def get_rsa(self):
        with open(self.rsa_key, 'r') as f:
            return RSA.importKey(f.read())


def tar_addbytes(tar, f, data):
    t = tarfile.TarInfo(f)
    t.size = len(data)
    tar.addfile(t, io.BytesIO(data))


class TwoStepEncryptFile(TwoStepBase):
    '''Encrypt a file with a fresh generated key, then encrypt the key with
    the root key. Then tar the encrypted file and the encrypted key together.

    '''
    PADDING = b'{'
    BLOCK_SIZE = 32

    output_key = 'file'
    def __init__(self, filename, **kw):
        super().__init__(**kw)
        self.filename = filename

    def transform(self, file):
        '''Encrypt file with AES 4096.

        Arguments:
            file: name of the file to be encrypted
            path: Location to save encrypted file
            default: current dir
        '''
        # Encrypt the file using AES and AES using RSA
        aes_key = Random.new().read(AES.key_size[2])
        with open(file, 'rb') as f:
            enc_message = base64.b64encode(
                AES.new(aes_key).encrypt(self.pad(f.read())))

        # Write encrypted file and encrypted key to tar
        fbase = os.path.basename(file)
        files = {
            fbase + '.enc': enc_message,
            fbase + '.key': self.get_rsa().encrypt(aes_key, 32)[0]
        }
        gz_fname = self.filename
        with tarfile.open(gz_fname, 'w') as tar:
            for f, data in files.items():
                tar_addbytes(tar, f, data)
        return gz_fname

    def pad(self, msg):
        n = self.BLOCK_SIZE - len(msg) % self.BLOCK_SIZE
        return msg + n * self.PADDING


class TwoStepDecryptFile(TwoStepBase):
    '''Decrypt a file encrypted with TwoStepEncryptFile.

    '''

    output_key = 'file'

    def transform(self, file):
        enc_file, enc_key = self.decompress(file)
        return self.decrypt(enc_file, enc_key)

    def decrypt(self, enc_file, enc_key):
        '''Decrypt file with AES 4096.

        Arguments:
            fname: name of the file to be encrypted
            path: Location to save encrypted file
            default: current dir
        '''
        return AES.new(self.get_rsa().decrypt(enc_key)).decrypt(
            base64.b64decode(enc_file)).rstrip('{')

    def decompress(self, filename):
        # write file and key to tar file
        with tarfile.open(filename, 'w') as tar:
            return (
                next(tar.extractfile(f) for f in tar.getmembers()
                     if f.name.endswith('.enc')),
                next(tar.extractfile(f) for f in tar.getmembers()
                     if f.name.endswith('.key')))
