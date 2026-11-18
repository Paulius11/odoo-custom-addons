from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    advance_customer_account_id = fields.Many2one(
        related="company_id.advance_customer_account_id", readonly=False
    )
    advance_vendor_account_id = fields.Many2one(
        related="company_id.advance_vendor_account_id", readonly=False
    )
