import os
import base64
import tarfile
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

from .block import Block


class TwoStepEncryptFile(Block):
    PADDING = b'{'
    BLOCK_SIZE = 32

    output_key = 'file'
    def __init__(self, *a, rsa_key, filename, **kw):
        super().__init__(*a, **kw)
        self.rsa_key = rsa_key
        self.filename = filename

    def run(self, file):
        enc_fname, key_fname = self.encrypt(file)
        compressed = self.compress(enc_fname, key_fname)
        return compressed

    def encrypt(self, fname):
        '''Encrypt file with AES 4096.
        Arguments:
            fname: name of the file to be encrypted
            path: Location to save encrypted file
            default: current dir
        '''
        # Encrypt the file using AES and AES using RSA
        aes_key = Random.new().read(AES.key_size[2])
        with open(fname, 'rb') as f:
            enc_message = base64.b64encode(
                AES.new(aes_key).encrypt(self.pad(f.read())))

        with open(self.rsa_key, 'r') as f:
            enc_key = RSA.importKey(f.read()).encrypt(aes_key, 32)

        # Write encrypted file and encrypted key
        enc_fname, key_fname = fname + '.enc', fname + '.key'
        with open(enc_fname, 'wb') as f:
            f.write(enc_message)
        with open(key_fname, 'wb') as f:
            f.write(enc_key[0])
        return enc_fname, key_fname

    def compress(self, *files):
        # write file and key to tar file
        gz_fname = self.filename
        with tarfile.open(gz_fname, 'w') as tar:
            for f in files:
                tar.add(f, arcname=os.path.basename(f))
        return gz_fname

    def pad(self, msg):
        n = self.BLOCK_SIZE - len(msg) % self.BLOCK_SIZE
        return msg + n * self.PADDING
