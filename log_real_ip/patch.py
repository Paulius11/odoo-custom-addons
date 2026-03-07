import logging
import werkzeug.serving
from odoo.tools import config

_logger = logging.getLogger(__name__)

_original_address_string = werkzeug.serving.WSGIRequestHandler.address_string

def _patched_address_string(self):
    xff = self.headers.get("X-Forwarded-For") or self.headers.get("X-Real-Ip")
    if xff:
        return xff.split(",")[0].strip()
    return _original_address_string(self)

if config.get("proxy_mode"):
    _logger.info("log_real_ip: patching werkzeug address_string to use X-Forwarded-For")
    werkzeug.serving.WSGIRequestHandler.address_string = _patched_address_string
