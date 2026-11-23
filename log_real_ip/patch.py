import ipaddress

from odoo.http.server import HTTPSocket
from odoo.tools import config

_original_make_environ = HTTPSocket._make_environ


def _client_ip(forwarded_for, real_ip):
    """The address the proxy saw. It appends to X-Forwarded-For, so only the last
    entry is its own; everything before comes from the client."""
    value = forwarded_for.rsplit(",", 1)[-1] if forwarded_for else real_ip or ""
    value = value.strip()
    if value.count(":") == 1:
        value = value.split(":")[0]  # IPv4 with a port
    if "%" in value:
        return None  # a zone id may hold any text
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return None
    return value


def _make_environ(self):
    environ = _original_make_environ(self)
    # Odoo does this only when the proxy also sends X-Forwarded-Host
    if config["proxy_mode"]:
        ip = _client_ip(
            environ.get("HTTP_X_FORWARDED_FOR"), environ.get("HTTP_X_REAL_IP")
        )
        if ip:
            self.ip = ip  # the log's address only: REMOTE_ADDR stays Odoo's decision
    return environ


HTTPSocket._make_environ = _make_environ
