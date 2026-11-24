import base64
import io
import socket
import threading
import time
from unittest.mock import patch

from PIL import Image, ImageDraw

from odoo.exceptions import UserError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tests.common import JsonRpcException

from odoo.addons.simple_pos_escpos_printer.models import escpos


class FakePrinter:
    """A TCP listener on localhost that keeps every job, like a printer on port 9100."""

    def __init__(self):
        self.sock = socket.create_server(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.jobs = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _addr = self.sock.accept()
            except OSError:
                return
            with conn:
                data = b""
                while chunk := conn.recv(65536):
                    data += chunk
                self.jobs.append(data)

    def wait_jobs(self, count=1):
        deadline = time.monotonic() + 3
        while len(self.jobs) < count and time.monotonic() < deadline:
            time.sleep(0.02)
        return self.jobs

    def close(self):
        self.sock.close()


def decode_job(job):
    """The printed image of one job (mode 1, black = 0) and its raster count."""
    assert job.startswith(escpos.INIT), job[:8]
    assert job.endswith(escpos.CUT), job[-8:]
    body, rows, blocks, width = job[len(escpos.INIT) : -len(escpos.CUT)], [], 0, None
    while body:
        assert body.startswith(escpos.RASTER), body[:8]
        width = int.from_bytes(body[4:6], "little")
        height = int.from_bytes(body[6:8], "little")
        rows.append(body[8 : 8 + width * height])
        body = body[8 + width * height :]
        blocks += 1
    image = Image.frombytes(
        "1", (width * 8, len(b"".join(rows)) // width), b"".join(rows)
    )
    return Image.eval(image.convert("L"), lambda v: 255 - v).convert("1"), blocks


def png(width, height, box=None, transparent=True):
    """A receipt-like PNG: transparent (or white) with a black box."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0) if transparent else "white")
    if box:
        ImageDraw.Draw(image).rectangle(box, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return base64.b64encode(buffer.getvalue()).decode()


@tagged("post_install", "-at_install")
class TestPosEscposPrinter(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fake = FakePrinter()
        cls.addClassCleanup(cls.fake.close)
        cls.printer = cls.env["pos.printer"].create(
            {
                "name": "Kitchen",
                "printer_type": "escpos_network",
                "escpos_host": "127.0.0.1",
                "escpos_port": cls.fake.port,
            }
        )
        cls.cashier = new_test_user(
            cls.env,
            "escpos_cashier",
            password="escpos_cashier",
            groups="base.group_user,point_of_sale.group_pos_user",
        )
        new_test_user(cls.env, "escpos_clerk", password="escpos_clerk")

    def setUp(self):
        super().setUp()
        self.fake.jobs.clear()

    def test_receipt_is_a_centered_raster_with_a_cut(self):
        result = self.printer._escpos_print_image(png(512, 100, box=(0, 10, 99, 19)))
        self.assertEqual(result, {"result": True})
        image, blocks = decode_job(self.fake.wait_jobs()[0])
        self.assertEqual(image.size, (576, 100))
        self.assertEqual(blocks, 1)
        # 512 px on 576 dots: 32 dots of margin; the box is at x 32..131, y 10..19
        self.assertEqual(image.getpixel((32, 10)), 0)
        self.assertEqual(image.getpixel((131, 19)), 0)
        self.assertEqual(image.getpixel((31, 10)), 255)
        self.assertEqual(image.getpixel((132, 10)), 255)
        # Transparent canvas margins print as white paper, not black
        self.assertEqual(image.getpixel((300, 50)), 255)

    def test_58mm_scales_the_receipt_down_and_long_ones_are_sliced(self):
        self.printer.escpos_paper = "58"
        self.printer._escpos_print_image(png(512, 800, transparent=False))
        image, blocks = decode_job(self.fake.wait_jobs()[0])
        self.assertEqual(image.size, (384, 600))
        self.assertEqual(blocks, 3, "600 rows in slices of 255")

    def test_cash_drawer(self):
        self.assertEqual(self.printer._escpos_open_cashbox(), {"result": True})
        self.assertEqual(self.fake.wait_jobs()[0], escpos.INIT + escpos.DRAWER)

    def test_unreachable_printer_says_so(self):
        free = socket.create_server(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        self.printer.escpos_port = port
        result = self.printer._escpos_print_image(png(100, 10))
        self.assertFalse(result["result"])
        self.assertIn("Not reachable from the Odoo server", result["message"])
        self.assertIn(f"127.0.0.1:{port}", result["message"])
        with self.assertRaisesRegex(UserError, "Not reachable"):
            self.printer.action_escpos_test_print()

    def test_unroutable_printer_times_out(self):
        # 192.0.2.1 is TEST-NET-1: never routed, so connect waits or fails at once
        self.printer.escpos_host = "192.0.2.1"
        with patch.object(escpos, "TIMEOUT", 0.5):
            result = self.printer._escpos_open_cashbox()
        self.assertFalse(result["result"])
        self.assertIn("192.0.2.1:", result["message"])

    def test_invalid_image(self):
        result = self.printer._escpos_print_image(base64.b64encode(b"not an image"))
        self.assertEqual(result["message"], "The receipt image is invalid.")
        self.assertFalse(self.fake.jobs)

    def test_test_print(self):
        action = self.printer.action_escpos_test_print()
        self.assertEqual(action["params"]["type"], "success")
        image, _blocks = decode_job(self.fake.wait_jobs()[0])
        self.assertEqual(image.width, 576)
        self.assertLess(image.getpixel((3, 3)), 255, "the frame is printed")

    def test_address_is_required(self):
        with self.assertRaises(ValidationError):
            self.printer.escpos_host = " "
        with self.assertRaises(ValidationError):
            self.printer.escpos_port = 0

    def test_print_route_for_a_pos_user(self):
        self.authenticate("escpos_cashier", "escpos_cashier")
        result = self.make_jsonrpc_request(
            "/simple_pos_escpos_printer/print",
            {"printer_id": self.printer.id, "image": png(64, 8)},
        )
        self.assertEqual(result, {"result": True})
        self.assertEqual(len(self.fake.wait_jobs()), 1)
        result = self.make_jsonrpc_request(
            "/simple_pos_escpos_printer/cashbox", {"printer_id": self.printer.id}
        )
        self.assertEqual(self.fake.wait_jobs(2)[1], escpos.INIT + escpos.DRAWER)

    def test_print_route_refuses_others(self):
        self.authenticate("escpos_clerk", "escpos_clerk")
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request(
                "/simple_pos_escpos_printer/print",
                {"printer_id": self.printer.id, "image": png(64, 8)},
            )
        self.authenticate("escpos_cashier", "escpos_cashier")
        epson = self.env["pos.printer"].create(
            {
                "name": "Epson",
                "printer_type": "epson_epos",
                "epson_printer_ip": "10.0.0.9",
            }
        )
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request(
                "/simple_pos_escpos_printer/cashbox", {"printer_id": epson.id}
            )
        self.assertFalse(self.fake.jobs)

    def test_settings_receipt_printer_and_cash_drawer(self):
        config = self.env["pos.config"].create({"name": "Front"})
        self.env["res.config.settings"].create(
            {
                "pos_config_id": config.id,
                "pos_escpos_receipt_printer_id": self.printer.id,
                "pos_iface_cashdrawer": True,
            }
        ).execute()
        self.assertEqual(config.escpos_receipt_printer_id, self.printer)
        self.assertTrue(config.iface_cashdrawer)
