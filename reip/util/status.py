'''


reip.blocks.Lambda(
    reip.util.mergedict(lambda: (
        reip.status.base,
        reip.status.cpu,
        reip.status.memory,
        reip.status.network,
        reip.status.wifi,
    ))
)


'''
import os
import re
import functools
import fnmatch
import socket
from datetime import datetime
import psutil
import ifcfg
import ixconfig
import netswitch
import reip
import logging

log = logging.getLogger(__name__)


STATS_FUNCTIONS = {}
def register_stats(func):
    @functools.wraps(func)
    def stats(*a, **kw):
        try:
            return func(*a, **kw)
        except Exception as e:
            log.exception(e)
            log.error('Error getting {} status: ({}) {}'.format(
                func.__name__, type(e).__name__, e))
        return {}
    STATS_FUNCTIONS[func.__name__] = stats
    return stats


# strip suffix from string if present
stripsfx = lambda x, sfx: x[:-len(sfx)] if x.endswith(sfx) else x
# find regex pattern in shell output
shfind = lambda pat, cmd: re.findall(pat, reip.util.shell.run(cmd)[0])
#
as_kw = lambda kw, key: kw if isinstance(kw, dict) else {key: kw}

# class Status(reip.Block):
#     def __init__(self, **kw):
#         super().__init__(**kw)
#
#     def process(self, meta):
#         data = {}
#         for key, func in STATS_FUNCTIONS.items():
#             try:
#                 data.update(func())
#             except Exception:
#                 self.log.exception()
#         return [data], {}
#


@register_stats
def cpu(meta=None):
    cpu_cur_freq = shfind(r'\b[\d]+', 'vcgencmd measure_clock arm')[-1].split()[0]
    cpu_temp = shfind(r'\b[\d?(.\d)]+\b', 'vcgencmd measure_temp')[0].split()[0]
    cpu_load = shfind(r'[\d(?/?.\d)]+', 'cat /proc/loadavg')
    cpu_model = shfind(r'Model\s*:\s*(.*)\s*', 'cat /proc/cpuinfo')[0]

    return {
        'cpu_model': cpu_model,
        'cpu_cur_freq': float(cpu_cur_freq),
        'cpu_temp': float(cpu_temp),
        'cpu_load_1': float(cpu_load[0]),
        'cpu_load_5': float(cpu_load[1]),
        'cpu_load_15': float(cpu_load[2]),
        'running_proc': int(cpu_load[3].split('/')[1]),
    }


@register_stats
def memory(meta=None):
    mem = psutil.virtual_memory()
    return {
        'mem_available': float(str(mem.available).replace('L', '')),
        'mem_used': float(str(mem.used).replace('L', '')),
        'mem_total': float(str(mem.total).replace('L', '')),
        'mem_percent': float(mem.percent)
    }

@register_stats
def git(meta=None, root=None):
    local_hash = reip.util.shell.git('rev-parse HEAD')
    remte_hash = reip.util.shell.git('rev-parse origin/master')
    return {
        'branch': reip.util.shell.git('rev-parse --abbrev-ref HEAD'),
        'commit_date': reip.util.shell.git('log -1 --format=%ci'),
        'commit': reip.util.shell.git('rev-parse --short HEAD'),
        'uptodate': int(local_hash == remte_hash)
    }

# network


@register_stats
def wifi(wlan='wlan*', meta=None):
    iwc = ixconfig.Iwc().ifaces(wlan)
    wlan = max(iwc or [None])
    return ({
        'wifi_quality': float(iwc[wlan].quality_ratio),
        'wifi_strength': float(iwc[wlan].strength),
        'ap': netswitch.Wpa().ssid
    } if wlan else {})


@register_stats
def cellular(cell_name='ppp0', cell_tty_commands='/dev/ttyUSB2', meta=None):
    if os.path.exists('/sys/class/net/%s' % cell_name):
        return {"cell_sig_stre": netswitch.cell.signal_strength(cell_tty_commands)}
    return {}


_IFC_MAP = {'ip': 'inet', 'mac': 'ether'}
DEFAULT_IFCONFIG = {
    'wlan0': _IFC_MAP,
    'eth0': _IFC_MAP,
    'tun0': {'ip': 'inet'},
}

@register_stats
def network(cfg=DEFAULT_IFCONFIG, meta=None):
    ifaces = ifcfg.interfaces()
    # wlan, tun, eth = (ifaces.get(i, {}) for i in ('wlan0', 'tun0', 'eth0'))
    return {
        'RX_packets': int(str(psutil.net_io_counters().bytes_recv).replace('L', '')),
        'TX_packets': int(str(psutil.net_io_counters().bytes_sent).replace('L', '')),
        **{
            '{}_{}'.format(pat, kname): ifaces.get(pat, {}).get(key)
            for pat, keys in cfg.items()
            # for name, ifcfg in ifaces.items()
            # if fnmatch.fnmatch(name, pat)
            for kname, key, in keys.items()
        }
    }


TYPES = {'bool': bool, 'int': int, 'str': str, 'float': float, '': lambda x: x}
def _search_usb(devices, pattern, cast=None):
    # find match
    match = next((
        d['name'] for d in devices
        if re.search(pattern, d['name'])), None)
    # cast to a type?
    for t in (cast or '').split('|'):
        match = TYPES[t](match)
    return match

@register_stats
def usb(meta=None, **devices):
    if not devices:
        return {}
    found_devices = reip.util.shell.lsusb()
    return {
        k: _search_usb(found_devices, **as_kw(kw, 'pattern'))
        for k, kw in devices.items()
    }


DEFAULT_STORAGE_LOCATIONS = {'root': '/', 'tmp': '/tmp', 'varlog': '/var/log'}

@register_stats
def storage(*poslocs, meta=None, **locs):
    locs.update({p.replace('/', '') or 'root': p for p in poslocs})
    locs = locs or DEFAULT_STORAGE_LOCATIONS
    return {
        '{}_usage'.format(k): psutil.disk_usage(path).percent
        for k, path in locs.items()
    }


def base(meta=None):
    return {
        'time': datetime.utcnow().isoformat(),
        'fqdn': socket.getfqdn(),# 'hostname'
    }

def meta(meta=None):
    return meta or {}
meta_ = meta

def full(include_meta=False):
    return reip.util.mergedict(base, cpu, memory, network, wifi, usb, storage, meta if include_meta else {})
