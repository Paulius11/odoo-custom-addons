import base64
import io
import logging

from PIL import Image, ImageDraw, ImageFont

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import escpos

_logger = logging.getLogger(__name__)


class PosPrinter(models.Model):
    _inherit = "pos.printer"

    printer_type = fields.Selection(
        selection_add=[
            ("escpos_network", "Use an ESC/POS network printer (via the Odoo server)")
        ],
        ondelete={"escpos_network": "set default"},
    )
    escpos_host = fields.Char(
        "Printer Address",
        help="IP address or host name of the printer, as the Odoo server sees it",
    )
    escpos_port = fields.Integer("Port", default=9100)
    escpos_paper = fields.Selection(
        [("80", "80 mm"), ("58", "58 mm")], "Paper Width", default="80"
    )

    @api.constrains("printer_type", "escpos_host", "escpos_port")
    def _check_escpos_address(self):
        for printer in self.filtered(lambda p: p.printer_type == "escpos_network"):
            if not (printer.escpos_host or "").strip():
                raise ValidationError(
                    self.env._("Enter the address of the ESC/POS printer.")
                )
            if not 0 < printer.escpos_port < 65536:
                raise ValidationError(
                    self.env._("The port must be between 1 and 65535.")
                )

    def _escpos_send(self, payload):
        """Send raw ESC/POS bytes. Returns {"result": bool, "message": str}."""
        self.ensure_one()
        host = self.escpos_host.strip()
        try:
            escpos.send(host, self.escpos_port, payload)
        except OSError as error:
            _logger.warning("ESC/POS printer %s (%s): %s", self.name, host, error)
            return {
                "result": False,
                "message": self.env._(
                    "Not reachable from the Odoo server at %(address)s (%(error)s).",
                    address=f"{host}:{self.escpos_port}",
                    error=error.strerror or str(error),
                ),
            }
        return {"result": True}

    def _escpos_print_image(self, image_b64):
        """Print a receipt image (base64 PNG or JPEG) and cut the paper."""
        self.ensure_one()
        try:
            payload = escpos.image_to_escpos(
                base64.b64decode(image_b64), self.escpos_paper or "80"
            )
        except (ValueError, OSError) as error:
            _logger.warning("ESC/POS printer %s: bad image: %s", self.name, error)
            return {
                "result": False,
                "message": self.env._("The receipt image is invalid."),
            }
        return self._escpos_send(payload)

    def _escpos_open_cashbox(self):
        self.ensure_one()
        return self._escpos_send(escpos.INIT + escpos.DRAWER)

    def action_escpos_test_print(self):
        """Print a small test ticket; raise an error the user can read when it fails."""
        self.ensure_one()
        lines = [
            self.env._("Test print"),
            self.name,
            f"{self.escpos_host}:{self.escpos_port}",
            self.env._("Paper: %(width)s mm", width=self.escpos_paper),
            fields.Datetime.to_string(fields.Datetime.now()),
        ]
        font = ImageFont.load_default(size=28)
        width = escpos.PAPER_DOTS[self.escpos_paper or "80"]
        image = Image.new("L", (width, 60 + 40 * len(lines)), 255)
        draw = ImageDraw.Draw(image)
        draw.rectangle((2, 2, width - 3, image.height - 3), outline=0, width=3)
        for i, line in enumerate(lines):
            draw.text((20, 30 + 40 * i), line, fill=0, font=font)
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        result = self._escpos_print_image(base64.b64encode(buffer.getvalue()))
        if not result["result"]:
            raise UserError(result["message"])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._(
                    "Test ticket sent to %(printer)s.", printer=self.name
                ),
            },
        }
