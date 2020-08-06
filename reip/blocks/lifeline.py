import ifcfg
from access_points import get_scanner
import reip


class WifiLifeline(reip.Block):
    wifi_scanner = None
    def __init__(self, *aps, iface='wlan0'):
        self.aps = aps
        self.iface = iface

    def init(self):
        self.wifi_scanner = get_scanner(self.iface)

    def process(self, meta):
        interfaces = list(ifcfg.interfaces())

        if self.iface not in interfaces:
            return  # interface is not available. don't do anything

        available_aps = self.available_aps()
        current_ap = self.current_ap()
        has_internet = internet_connected(self.iface)
        connected, available = False, False

        # check each ap
        for ap in self.aps:
            available = ap in available_aps
            if ap == current_ap and has_internet:  # already connected
                connected = True
                break
            connected = available and self.connect_ap(ap)
            if connected and internet_connected(self.iface):
                current_ap = ap
                break
        else:
            return  # desired aps are not available. Don't do anything

        return None, {
            'available_aps': available_aps,
            'current_ap': current_ap.ssid,
            'available': available,
            'connected': connected,
            'quality': current_ap.quality,
        }

    def current_ap(self):
        # TODO: read current wpa supplicant file
        return 'asdfasdf'

    def available_aps(self):
        return {
            ap.ssid: ap for ap in sorted(
                self.wifi_scanner.get_access_points(),
                key=lambda ap: ap.quality, reverse=True)
        }

    def connect_ap(self, ap):
        # TODO: swap wpa supplicant files
        restart_iface(self.iface)


def internet_connected(iface=None, n=3):
    '''Check if we're connected to the internet (optionally, check a specific interface `iface`)'''
    return not reip.util.shell.run(
        "ping {args} 8.8.8.8 >/dev/null 2>&1", args=dict(I=iface, c=n)).out

def restart_iface(iface=None, sleep=5):
    '''Restart the specified network interface. Returns True if restarted without error.'''
    try:
        reip.util.shell.run(f'ifdown {iface} --force && sleep {sleep}')
    finally:
        reip.util.shell.run(f'ifup {iface} --force && sleep {sleep}')
    return True
