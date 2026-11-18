from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Core payments only post to receivable/payable-type accounts, so a customer
    # deposit uses a payable-type (liability) account and a vendor prepayment a
    # receivable-type (asset) account, each separate from the partner's own.
    advance_customer_account_id = fields.Many2one(
        "account.account",
        string="Customer Advances Account",
        domain="[('account_type', '=', 'liability_payable'), ('reconcile', '=', True)]",
        check_company=True,
    )
    advance_vendor_account_id = fields.Many2one(
        "account.account",
        string="Vendor Prepayments Account",
        domain="[('account_type', '=', 'asset_receivable'), ('reconcile', '=', True)]",
        check_company=True,
    )
