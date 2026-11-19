from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    escpos_receipt_printer_id = fields.Many2one(
        "pos.printer",
        string="ESC/POS Receipt Printer",
        domain=[("printer_type", "=", "escpos_network")],
        help="Receipts print here, through the Odoo server; the cash drawer is the one "
        "wired to this printer",
    )
