import ipaddress
import logging

import werkzeug.serving

from odoo.tools import config

_logger = logging.getLogger(__name__)

_original_address_string = werkzeug.serving.WSGIRequestHandler.address_string


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


def _patched_address_string(self):
    ip = _client_ip(
        ",".join(self.headers.get_all("X-Forwarded-For") or []),
        self.headers.get("X-Real-Ip"),
    )
    return ip or _original_address_string(self)


if config.get("proxy_mode"):
    _logger.info("log_real_ip: patching werkzeug address_string to use X-Forwarded-For")
    werkzeug.serving.WSGIRequestHandler.address_string = _patched_address_string
