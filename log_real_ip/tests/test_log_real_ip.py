from unittest.mock import patch

import h11

from odoo.http.server import HTTPSocket
from odoo.tests import TransactionCase, tagged
from odoo.tools import config

PEER = "172.19.0.1"


@tagged("post_install", "-at_install")
class TestLogRealIp(TransactionCase):
    def _logged(self, *headers, proxy_mode=True):
        socket = HTTPSocket(None, (PEER, 40000))
        socket.h11request = h11.Request(
            method="GET", target="/", headers=[("Host", "odoo.example"), *headers]
        )
        with patch.dict(config.options, {"proxy_mode": proxy_mode}):
            socket._make_environ()
        return socket.ip

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

    def test_forwarded_host(self):
        ip = self._logged(
            ("X-Forwarded-For", "6.6.6.6, 198.51.100.7"),
            ("X-Forwarded-Host", "odoo.example"),
        )
        self.assertEqual(ip, "198.51.100.7")

    def test_ignored_without_proxy_mode(self):
        headers = ("X-Forwarded-For", "198.51.100.7")
        self.assertEqual(self._logged(headers, proxy_mode=False), PEER)
