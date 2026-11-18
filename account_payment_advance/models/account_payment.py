from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_advance = fields.Boolean(
        "Advance",
        copy=False,
        help="Post the payment on the advance account of the company instead of the "
        "partner's receivable or payable, to apply it to an invoice or bill later.",
    )
    advance_residual = fields.Monetary(
        "Unapplied",
        compute="_compute_advance_residual",
        store=True,
        currency_field="company_currency_id",
    )

    @api.depends("is_advance")
    def _compute_destination_account_id(self):
        res = super()._compute_destination_account_id()
        for pay in self.filtered("is_advance"):
            # without the account set, keep core's; action_post refuses the payment
            pay.destination_account_id = (
                pay._advance_account() or pay.destination_account_id
            )
        return res

    def _advance_account(self):
        self.ensure_one()
        company = self.company_id
        if self.partner_type == "customer":
            return company.advance_customer_account_id
        return company.advance_vendor_account_id

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        # a draft payment's journal entry must follow the account when Advance is ticked
        return super()._get_trigger_fields_to_synchronize() + ("is_advance",)

    def _advance_lines(self):
        """The payment's journal items on its advance account."""
        self.ensure_one()
        return self.move_id.line_ids.filtered(
            lambda line: (
                self.is_advance
                and line.account_id == self.destination_account_id
                and line.move_id.state == "posted"
            )
        )

    @api.depends(
        "is_advance",
        "destination_account_id",
        "move_id.state",
        "move_id.line_ids.amount_residual",
    )
    def _compute_advance_residual(self):
        for pay in self:
            pay.advance_residual = abs(
                sum(pay._advance_lines().mapped("amount_residual"))
            )

    def action_post(self):
        for pay in self.filtered("is_advance"):
            if not pay._advance_account():
                raise UserError(
                    self.env._(
                        "Set the customer advances and vendor prepayments accounts in "
                        "Accounting settings before posting an advance."
                    )
                )
            if pay.destination_account_id != pay._advance_account():
                raise UserError(
                    self.env._(
                        "%s is an advance; it must post on the advance account.",
                        pay.name,
                    )
                )
        return super().action_post()
