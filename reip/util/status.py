'''


reip.blocks.Lambda(
    reip.util.mergedict(lambda: (
        reip.status.meta,
        reip.status.cpu,
        reip.status.memory,
        reip.status.network,
        reip.status.wifi,
    ))
)


'''
import os
import re
import socket
from datetime import datetime
import psutil
import ifcfg
import ixconfig
import netswitch
import reip


STATS_FUNCTIONS = {}
def register_stats(func):
    STATS_FUNCTIONS[func.__name__] = func
    return func


# strip suffix from string if present
stripsfx = lambda x, sfx: x[:-len(sfx)] if x.endswith(sfx) else x
# find regex pattern in shell output
shfind = lambda pat, cmd: re.findall(pat, reip.util.shell.run(cmd)[0])


class Status(reip.Block):
    def __init__(self, **kw):
        super().__init__(**kw)

    def process(self, meta):
        data = {}
        for key, func in STATS_FUNCTIONS.items():
            try:
                data.update(func())
            except Exception:
                self.log.exception()
        return [data], {}



@register_stats
def cpu():
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
def memory():
    mem = psutil.virtual_memory()
    return {
        'mem_available': float(str(mem.available).replace('L', '')),
        'mem_used': float(str(mem.used).replace('L', '')),
        'mem_total': float(str(mem.total).replace('L', '')),
        'mem_percent': float(mem.percent)
    }


# network


@register_stats
def wifi(wlan='wlan*'):
    iwc = ixconfig.Iwc().ifaces(wlan)
    wlan = next(iwc, None)
    return ({
        'wifi_quality': float(iwc[wlan].quality_ratio),
        'wifi_strength': float(iwc[wlan].strength),
        'AP': netswitch.Wpa().ssid
    } if wlan else {})


@register_stats
def cellular(cell_name='ppp0', cell_tty_commands=''):
    if os.path.exists('/sys/class/net/%s' % cell_name):
        return {"cell_sig_stre": netswitch.cell.signal_strength(cell_tty_commands)}
    return {}


@register_stats
def network():
    ifaces = ifcfg.interfaces()
    wlan, tun, eth = (ifaces.get(i, {}) for i in ('wlan0', 'tun0', 'eth0'))
    return {
        'RX_packets': int(str(psutil.net_io_counters().bytes_recv).replace('L', '')),
        'TX_packets': int(str(psutil.net_io_counters().bytes_sent).replace('L', '')),
        'wlan0_ip': wlan.get('inet'),
        'wlan0_mac': wlan.get('ether'),
        'tun0_ip': tun.get('inet'),
        'eth0_mac': eth.get('ether'),
        'eth0_ip': eth.get('inet'),
    }


def meta():
    return {
        'time': datetime.utcnow().isoformat(),
        'hostname': socket.getfqdn(),
    }

def full():
    return reip.util.mergedict(meta, cpu, memory, network, wifi)
