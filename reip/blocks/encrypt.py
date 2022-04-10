import os
import io
import base64
import tarfile
from Crypto import Random
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Util import Padding

import reip


class TwoStageEncrypt(reip.Block):
    '''Encrypt a file with a fresh generated key, then encrypt the key with
    the root key. Then tar the encrypted file and the encrypted key together.
    '''
    #PADDING = b'{'
    BLOCK_SIZE = 32

    def __init__(self, filename, rsa_key, remove_files=False, extra_files=None, is_rsa_key_file=True, **kw):
        super().__init__(**kw)
        self.filename = str(filename)
        self.remove_files = remove_files
        self.gz = self.filename.endswith('.gz')
        self.extra_files = extra_files

        if is_rsa_key_file:
            if not os.path.isfile(rsa_key):
                raise OSError("No rsa key found.")
            with open(rsa_key, 'r') as f:
                rsa_key = f.read()
        self.public_key = RSA.importKey(str(rsa_key))
        self.cipher = PKCS1_OAEP.new(self.public_key)


    def process(self, file, meta):
        '''Encrypt file with AES 4096.
        Arguments:
            file: name of the file to be encrypted
            path: Location to save encrypted file
            default: current dir
        '''
        fname = reip.util.ensure_dir(self.filename.format(
            name=reip.util.fname(file), fname=os.path.basename(file), **meta))

        with open(file, 'rb') as f:
            enc_message = f.read()

        enc = self.encrypt(enc_message, os.path.basename(file))

        extra_files = reip.util.resolve_call(self.extra_files, file, meta=meta) or {}
        enc.update(extra_files)

        compressed = self.compress(enc, fname)
        self.maybe_remove_files(file)
        return [compressed], {}

    def encrypt(self, msg, name='file'):
        # Encrypt the file using AES and AES using RSA
        aes_key = Random.new().read(AES.key_size[2])
        key = AES.new(aes_key, AES.MODE_CBC)

        msg = Padding.pad(msg, AES.block_size)
        msg = key.iv + key.encrypt(msg)
        msg = base64.b64encode(msg)

        # gather files
        return {
            name+'.enc': msg,
            name+'.key': self.cipher.encrypt(aes_key)
        }

    def compress(self, files, out_file):
        # write tar
        with tarfile.open(out_file, 'w:gz' if self.gz else 'w') as tar:
            for f, data in files.items():
                tar_addbytes(tar, f, data)
        return out_file

    def maybe_remove_files(self, *files):
        if self.remove_files:
            for f in files:
                os.remove(f)


class TwoStageDecrypt(reip.Block):
    '''Decrypt a file encrypted with TwoStepEncryptFile.
    '''
    PADDING = b'{'
    BLOCK_SIZE = 32

    def __init__(self, filename, rsa_key, remove_files=False, **kw):
        super().__init__(**kw)
        self.filename = str(filename)
        self.remove_files = remove_files

        if os.path.isfile(rsa_key):
            with open(rsa_key, 'r') as f:
                rsa_key = f.read()
        self.private_key = RSA.importKey(rsa_key)
        self.cipher = PKCS1_OAEP.new(self.private_key)

    def process(self, file, meta=None):
        # get the output filename and make sure the parent dir exists
        fname = reip.util.ensure_dir(self.filename.format(
            name=reip.util.fname(file), **meta))
        # decrypt file to disk
        enc_msg, enc_key = self.decompress(file)
        decrypted = self.decrypt(enc_msg, enc_key)
        with open(fname, 'wb') as f:
            f.write(decrypted)

        self.maybe_remove_files(file)
        return [fname], {}

    def decrypt(self, msg, enc_key):
        '''Decrypt file with AES 4096.'''
        msg = base64.b64decode(msg)

        iv, msg = msg[:AES.block_size], msg[AES.block_size:]
        aes_key = self.cipher.decrypt(enc_key)
        key = AES.new(aes_key, AES.MODE_CBC, iv)

        msg = key.decrypt(msg)
        msg = Padding.unpad(msg, AES.block_size)
        return msg

    def decompress(self, filename):
        # write file and key to tar file
        with tarfile.open(filename, 'r') as tar:
            return (
                next(tar.extractfile(f).read() for f in tar.getmembers()
                     if f.name.endswith('.enc')),
                next(tar.extractfile(f).read() for f in tar.getmembers()
                     if f.name.endswith('.key'))
            )

    def maybe_remove_files(self, *files):
        if self.remove_files:
            for f in files:
                os.remove(f)


def get_private_key(public_fname):
    private_fname = public2private(public_fname)
    return private_fname if os.path.isfile(private_fname) else public_fname


def public2private(public_fname):
    return '{}_private{}'.format(*os.path.splitext(public_fname))

def private2public(private_fname):
    return '{}.pub'.format(private_fname)

def load_rsa(rsa_key):
    with open(rsa_key, 'rb') as f:
        return RSA.importKey(f.read())

def create_rsa(private_fname=None, public_fname=None, bits=2048):
    private_key = RSA.generate(bits, e=65537)
    public_key = private_key.publickey()

    if not (private_fname or public_fname):
        private_fname = os.path.expanduser('~/.ssh/encrypt_rsa')
    private_fname = private_fname or public2private(public_fname)
    public_fname = public_fname or private2public(private_fname)

    reip.util.ensure_dir(public_fname)
    with open(public_fname, 'wb') as f:
        f.write(public_key.exportKey("PEM"))
    with open(private_fname, 'wb') as f:
        f.write(private_key.exportKey("PEM"))
    return private_fname, public_fname

def tar_addbytes(tar, f, data):
    t = tarfile.TarInfo(f)
    t.size = len(data)
    tar.addfile(t, io.BytesIO(data))