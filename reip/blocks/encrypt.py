import os
import io
import base64
import tarfile
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

import reip


class TwoStageEncrypt(reip.Block):
    '''Encrypt a file with a fresh generated key, then encrypt the key with
    the root key. Then tar the encrypted file and the encrypted key together.
    '''
    PADDING = b'{'
    BLOCK_SIZE = 32

    def __init__(self, filename, rsa_key, **kw):
        super().__init__(**kw)
        self.filename = filename
        self.public_key = rsa_key
        if not os.path.isfile(self.public_key):
            create_rsa(self.public_key)

    def process(self, file, meta):
        '''Encrypt file with AES 4096.
        Arguments:
            file: name of the file to be encrypted
            path: Location to save encrypted file
            default: current dir
        '''
        fname = reip.util.ensure_dir(self.filename.format(**meta))
        return [self.compress(self.encrypt(file), fname)], {}

    def encrypt(self, file):
        # Encrypt the file using AES and AES using RSA
        aes_key = Random.new().read(AES.key_size[2])
        with open(file, 'rb') as f:
            enc_message = base64.b64encode(
                AES.new(aes_key).encrypt(self.pad(f.read())))
        # gather files
        fbase = os.path.basename(file)
        files = {
            fbase + '.enc': enc_message,
            fbase + '.key': load_rsa(self.public_key).encrypt(aes_key, 32)[0]
        }
        return files

    def compress(self, files, out_file):
        # write tar
        with tarfile.open(out_file, 'w') as tar:
            for f, data in files.items():
                tar_addbytes(tar, f, data)
                print(tar.getmembers())
        return out_file

    def pad(self, msg):
        n = self.BLOCK_SIZE - len(msg) % self.BLOCK_SIZE
        return msg + n * self.PADDING


class TwoStageDecrypt(reip.Block):
    '''Decrypt a file encrypted with TwoStepEncryptFile.
    '''
    def __init__(self, filename, rsa_key, **kw):
        super().__init__(**kw)
        self.filename = filename
        self.private_key = rsa_key

    def process(self, file, meta=None):
        # get the output filename and make sure the parent dir exists
        fname = reip.util.ensure_dir(self.filename.format(**meta))
        # decrypt file to disk
        enc_file, enc_key = self.decompress(file)
        return [self.decrypt(enc_file, enc_key, fname)], {}

    def decrypt(self, enc_file, enc_key, fname):
        '''Decrypt file with AES 4096.'''
        with open(fname, 'w') as f:
            f.write(
                AES.new(load_rsa(self.private_key).decrypt(enc_key)).decrypt(
                    base64.b64decode(enc_file)).rstrip('{'))
        return fname

    def decompress(self, filename):
        # write file and key to tar file
        with tarfile.open(filename, 'w') as tar:
            print(tar.getmembers())
            return (
                next(tar.extractfile(f) for f in tar.getmembers()
                     if f.name.endswith('.enc')),
                next(tar.extractfile(f) for f in tar.getmembers()
                     if f.name.endswith('.key'))
            )

def load_rsa(rsa_key):
    with open(rsa_key, 'rb') as f:
        return RSA.importKey(f.read())

def create_rsa(rsa_key, bits=2048):
    private_key = RSA.generate(bits, e=65537)
    public_key = private_key.publickey()

    public_fname = rsa_key
    private_fname = '{}_private{}'.format(*os.path.splitext(public_fname))
    print('Creating RSA Key Pair:')
    print('\tprivate:', private_fname)
    print('\tpublic:', public_fname)

    reip.util.ensure_dir(public_fname)
    with open(public_fname, 'wb') as f:
        print(99999999999999999, public_fname, public_key.exportKey("PEM"))
        f.write(public_key.exportKey("PEM"))
    with open(private_fname, 'wb') as f:
        print(99999999999999999, private_fname, private_key.exportKey("PEM"))
        f.write(private_key.exportKey("PEM"))
    return private_fname, private_fname

def tar_addbytes(tar, f, data):
    t = tarfile.TarInfo(f)
    t.size = len(data)
    tar.addfile(t, io.BytesIO(data))
