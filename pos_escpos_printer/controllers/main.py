from odoo import http
from odoo.exceptions import UserError
from odoo.http import request


class PosEscposPrinter(http.Controller):
    """Print jobs from the POS. The browser sends a printer id, never an address:
    only POS managers set where the server connects to."""

    def _printer(self, printer_id):
        printer = request.env["pos.printer"].browse(int(printer_id)).exists()
        printer.check_access("read")
        if printer.printer_type != "escpos_network":
            raise UserError(request.env._("This is not an ESC/POS network printer."))
        return printer

    @http.route("/pos_escpos_printer/print", type="jsonrpc", auth="user")
    def print_image(self, printer_id, image):
        return self._printer(printer_id)._escpos_print_image(image)

    @http.route("/pos_escpos_printer/cashbox", type="jsonrpc", auth="user")
    def open_cashbox(self, printer_id):
        return self._printer(printer_id)._escpos_open_cashbox()
