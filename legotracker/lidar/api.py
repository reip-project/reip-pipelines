from __future__ import unicode_literals

import reip
import socket

class OS1ConfigurationError(Exception):
    pass

class OS1API(object):
    def __init__(self, host, port=7501):
        self.address = (host, port)
        self._error = None

    def get_config_txt(self):
        return self._send("get_config_txt")

    def get_sensor_info(self):
        return self._send("get_sensor_info")

    def get_beam_intrinsics(self):
        return self._send("get_beam_intrinsics")

    def get_imu_intrinsics(self):
        return self._send("get_imu_intrinsics")

    def get_lidar_intrinsics(self):
        return self._send("get_lidar_intrinsics")

    def get_config_param(self, *args):
        command = "get_config_param {}".format(" ".join(args))
        return self._send(command)

    def set_config_param(self, *args):
        command = "set_config_param {}".format(" ".join(args))
        return self._send(command)

    def reinitialize(self):
        return self._send("reinitialize")

    def raise_for_error(self):
        if self.has_error:
            raise OS1ConfigurationError(self._error)

    @property
    def has_error(self):
        if self._error is not None:
            return True
        return False

    def _send(self, command, *args):
        self._error = None
        payload = " ".join([command] + list(args)).encode("utf-8") + b"\n"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(self.address)
            sock.sendall(payload)
            response = b""
            while not response.endswith(b"\n"):
                response += sock.recv(1024)
        self._error_check(response)
        return response.decode("utf-8")

    def _error_check(self, response):
        response = response.decode("utf-8")
        if response.startswith("error"):
            self._error = response
        else:
            self._error = None