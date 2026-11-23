from email.message import Message
from types import SimpleNamespace

from odoo.tests import TransactionCase, tagged

from odoo.addons.log_real_ip import patch

PEER = "172.19.0.1"


@tagged("post_install", "-at_install")
class TestLogRealIp(TransactionCase):
    def _logged(self, *headers):
        message = Message()
        for name, value in headers:
            message[name] = value
        handler = SimpleNamespace(
            headers=message, environ=None, client_address=(PEER, 40000)
        )
        return patch._patched_address_string(handler)

    def test_client_cannot_forge_the_first_entry(self):
        ip = self._logged(("X-Forwarded-For", "6.6.6.6, 198.51.100.7"))
        self.assertEqual(ip, "198.51.100.7")

    def test_client_cannot_forge_with_its_own_header(self):
        ip = self._logged(
            ("X-Forwarded-For", "6.6.6.6"), ("X-Forwarded-For", "198.51.100.7")
        )
        self.assertEqual(ip, "198.51.100.7")

    def test_only_addresses_are_logged(self):
        self.assertEqual(self._logged(("X-Forwarded-For", '1.2.3.4 - "GET /')), PEER)
        self.assertEqual(self._logged(("X-Real-Ip", "not an address")), PEER)

    def test_real_ip_fallback(self):
        self.assertEqual(self._logged(("X-Real-Ip", "198.51.100.8")), "198.51.100.8")

    def test_ipv6_and_port(self):
        self.assertEqual(
            self._logged(("X-Forwarded-For", "2001:db8::7")), "2001:db8::7"
        )
        ip = self._logged(("X-Forwarded-For", "198.51.100.7:51234"))
        self.assertEqual(ip, "198.51.100.7")

    def test_no_header(self):
        self.assertEqual(self._logged(), PEER)
