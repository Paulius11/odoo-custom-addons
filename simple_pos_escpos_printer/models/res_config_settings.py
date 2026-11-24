from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_escpos_receipt_printer_id = fields.Many2one(
        related="pos_config_id.escpos_receipt_printer_id", readonly=False
    )

    @api.model
    def _is_cashdrawer_displayed(self, res_config):
        return super()._is_cashdrawer_displayed(res_config) or bool(
            res_config.pos_escpos_receipt_printer_id
        )

    @api.depends(
        "pos_iface_print_via_proxy",
        "pos_config_id",
        "pos_epson_printer_ip",
        "pos_other_devices",
        "pos_escpos_receipt_printer_id",
    )
    def _compute_pos_iface_cashdrawer(self):
        return super()._compute_pos_iface_cashdrawer()
