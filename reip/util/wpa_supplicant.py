'''Utils for managing wpa supplicant files.
'''
import os
import time
from shutil import copyfile
from sonycnode.utils import misc
from sonycnode.utils import sonyc_logger as loggerClass
from sonycnode.utils.settings import config, confuse


logger = loggerClass.sonyclogger(loggername="WpaSupplicant")

cfg = config['network'].get({
    'ap_path': confuse.Filename('/etc/wpa_supplicant/aps'),
    'wlan_name': 'wlan0',
})

REPO_AP_PATH = os.path.join(os.path.dirname(__file__), 'aps')
WPA_FNAME = "/etc/wpa_supplicant/wpa_supplicant.conf"
AP_PATH = cfg.ap_path
AP_PATTERN = os.path.join(cfg.ap_path, '{}.conf')

os.makedirs(cfg.ap_path, exist_ok=True)


def connect(ssid):
    return Wpa(ssid).connect()


class Wpa:
    def __init__(self, ssid=None, path=None):
        self.path = path or (Wpa.ssid_path(ssid) if ssid else WPA_FNAME)
        self.ssid = ssid or self.parsed.get('ssid')

    @misc.log_error_as_error(logger, msg="Error connecting to ap: ", default=False)
    def connect(self, backup=True):
        '''Set ap as current wpa_supplicant.'''
        wpa = Wpa()
        if wpa.ssid != self.ssid:
            if backup:
                wpa.backup()
            return self.copy(WPA_FNAME) and restart_iface(cfg.wlan_name)
        return True

    @misc.log_error_as_error(logger, msg="Error copying wpa_supplicant: ", default=False)
    def copy(self, dest):
        '''Copy wpa_supplicant to destination.'''
        if self.path != dest:
            copyfile(self.path, dest)
        return True

    def create(self, **kw):
        '''Generate wpa supplicant.'''
        generate_wpa_config(self.ssid, **kw)

    @misc.log_error_as_error(logger, msg="Error copying to wpa_supplicant: ", default=False)
    def backup(self, force=True):
        '''Make sure that the current wifi network is present in aps/.
        '''
        if force or self.ssid not in ssids_from_dir(cfg.ap_path):
            self.copy(self.ssid_path(self.ssid))
            return True
        return False

    @misc.cached_property
    def parsed(self):
        '''Parse the wpa_supplicant.conf file and return key value pairs.'''
        DROP_KEYS = ('network',)
        with open(self.path) as wpa_conf:
            return {
                x[0].strip(): x[1].strip('" ') for x in
                (l.split("=", 1) for l in wpa_conf.read().splitlines())
                if len(x) > 1 and x[0] not in DROP_KEYS
            }

    def __getattr__(self, k):
        try:
            return self.parsed[k]
        except KeyError as e:
            raise AttributeError(e)

    @staticmethod
    def ssid_path(ssid):
        return AP_PATTERN.format(ssid)




def ssids_from_dir(ap_path=cfg.ap_path, pat='*.conf'):
    '''Get file name -> file path mapping for files in a directory.
    e.g.: `{file: ap_path/file.ext for f in glob(ap_path)}`'''
    return {
        os.path.splitext(os.path.basename(f))[0]: f
        for f in misc.prodiglob(ap_path, pat)}

def sync_ap_directory(repo_path=REPO_AP_PATH, ap_path=cfg.ap_path, force=True, backup=True):
    '''Copy aps from network/aps to the trusted aps path.'''
    fnames_repo = ssids_from_dir(repo_path)
    fnames_aps = ssids_from_dir(ap_path)
    for fn in (fnames_repo if force else set(fnames_repo) - set(fnames_aps)):
        copyfile(fnames_repo[fn], os.path.join(ap_path, fn + '.conf'))
    if backup:
        Wpa().backup()





@misc.log_error_as_error(logger, msg="Error restarting interface: ")
def restart_iface(ifname=None, sleep=5):
    '''Restart the specified network interface. Returns True if restarted without error.'''
    logger.info("Restarting Interface")
    o, err = misc.execute('sudo ifdown {} --force && sleep {}'.format(ifname, sleep))
    #logger.info('ifdown: {} || {}'.format(o, err))
    time.sleep(sleep)
    o, err = misc.execute('sudo ifup {} && sleep {}'.format(ifname, sleep))
    #logger.info('ifup: {} || {}'.format(o, err))
    return True



'''

Create Wpa Supplicant File

'''


@misc.log_error_as_error(logger, msg="Error creating wpa_supplicant: ", default=False)
def generate_wpa_config(ssid, password=None, kind='basic', group='netdev', country='US', **kw):
    '''Create the wpa_supplicant configuration file
    in the `./aps/{ssid}.conf`

    Arguments:
        ssid (str): Access point to add credentials for.
        password (str, optional): The

    Returns:
        status (bool): True if no exception was raised when creating
    '''
    logger.debug("Creating config for: " + str(ssid))
    if kind == 'basic':
        if password:
            network = dict(ssid=ssid, psk=password)
        else:
            network = dict(ssid=ssid, key_mgmt='NONE')
    elif kind == 'wpa-eap':
        network = dict(
            ssid=ssid, proto='RSN', key_mgmt='WPA-EAP',
            pairwise='CCMP', phase2="auth=MSCHAPV2",
            auth_alg='OPEN', eap='PEAP',
            identity=kw.pop('identity'),
            password=password)
    else:
        raise ValueError('Unknown wpa config format "{}"'.format(kind))

    tmpl = misc.redent('''
        ctrl_interface=DIR=/var/run/wpa_supplicant GROUP={group}
        update_config=1
        country={country}
        network={
        {network}
        }'''.strip())
    with open(Wpa.ssid_path(ssid), 'w') as f:
        f.write(tmpl.format(
            group=group, country=country,
            network=misc.redent(_wpa_keys(**network, **kw), 2)))
    return True


def _wpa_keys(*a, sep='\n', **kw):
    return sep.join(
        list(map(str, a)) +
        ['{}={}'.format(k, '"{}"'.format(v) if not isinstance(v, (int, float)) else v)
         for k, v in kw.items()])

def askpass():
    import getpass
    return getpass.getpass()
