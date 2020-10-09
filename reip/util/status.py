import re
import socket
from datetime import datetime
import netswitch
import psutil
import ifcfg
import reip


STATS_FUNCTIONS = {}
def register_stats(name=None, func=None):
    def inner(func, name=name):
        name = name or stripsfx(func.__name__, 'Stats')
        func = misc.log_error_as_error(logger, default=dict)(func)
        STATS_FUNCTIONS[name] = func
        return func
    return (
        # @register_stats
        inner(name, name=None) if callable(name)
        # register_stats('misc', lambda: dict('a': 5))
        else inner(func, name=name) if callable(func)
        # @register_stats('misc')
        else inner)


# strip suffix from string if present
stripsfx = lambda x, sfx: x[:-len(sfx)] if x.endswith(sfx) else x
# find regex pattern in shell output
shfind = lambda pat, cmd: re.findall(pat, reip.util.shell.run(cmd)[0])



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
def wifi_quality():
    iwc = ixconfig.Iwc(cfgnet.wlan_name)
    return ({"sig_qual": float(iwc.quality), "sig_stre": float(iwc.strength)}
            if iwc.params else {})


@register_stats
def cellular():
    if os.path.exists('/sys/class/net/%s' % cfgnet.cell_name):
        return {"cell_sig_stre": cell.signal_strength(cfgnet.cell_tty_commands)}
    return {}


@register_stats
def network():
    ifaces = ifcfg.interfaces()
    wlan, tun, eth = (ifaces.get(i, {}) for i in ('wlan0', 'tun0', 'eth0'))

    return {
        'AP': netswitch.Wpa().ssid,
        'RX_packets': int(str(psutil.net_io_counters().bytes_recv).replace('L', '')),
        'TX_packets': int(str(psutil.net_io_counters().bytes_sent).replace('L', '')),
        'wlan0_ip': wlan.get('inet'),
        'wlan0_mac': wlan.get('ether'),
        'tun0_ip': tun.get('inet'),
        'eth0_mac': eth.get('ether'),
        'eth0_ip': eth.get('inet'),
    }


def statusInfo():
    return {
        'time': datetime.utcnow().isoformat(),
        'fqdn': socket.getfqdn(),
        'deployment_id': node_state.deployment_id,
    }
