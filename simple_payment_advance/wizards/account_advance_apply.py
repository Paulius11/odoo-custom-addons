from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountAdvanceApply(models.TransientModel):
    _name = "account.advance.apply"
    _description = "Apply an Advance"

    move_id = fields.Many2one(
        "account.move", string="Invoice or Bill", required=True, readonly=True
    )
    currency_id = fields.Many2one(related="move_id.company_currency_id")
    available_payment_ids = fields.Many2many(
        "account.payment", compute="_compute_available_payment_ids"
    )
    payment_id = fields.Many2one(
        "account.payment",
        string="Advance",
        required=True,
        domain="[('id', 'in', available_payment_ids)]",
    )
    advance_residual = fields.Monetary(related="payment_id.advance_residual")
    amount = fields.Monetary(
        compute="_compute_amount", store=True, readonly=False, required=True
    )

    @api.depends("move_id")
    def _compute_available_payment_ids(self):
        for wizard in self:
            wizard.available_payment_ids = self.env["account.payment"].search(
                wizard.move_id._open_advances_domain(), order="date, id"
            )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        move = self.env["account.move"].browse(values.get("move_id"))
        if move and "payment_id" in fields_list:
            # the oldest advance first, as accountants apply them
            first = self.env["account.payment"].search(
                move._open_advances_domain(), order="date, id", limit=1
            )
            values["payment_id"] = first.id
        return values

    @api.depends("payment_id")
    def _compute_amount(self):
        for wizard in self:
            wizard.amount = min(
                wizard.payment_id.advance_residual, wizard.move_id.amount_residual
            )

    def action_apply(self):
        self.ensure_one()
        move, payment = self.move_id, self.payment_id
        if payment not in self.available_payment_ids:
            raise UserError(
                _(
                    "%(advance)s cannot be applied to %(move)s.",
                    advance=payment.name,
                    move=move.name,
                )
            )
        currency = self.currency_id
        if currency.compare_amounts(self.amount, 0) <= 0:
            raise UserError(_("The amount to apply must be positive."))
        if currency.compare_amounts(self.amount, payment.advance_residual) > 0:
            raise UserError(_("The amount is more than what is left of the advance."))
        if currency.compare_amounts(self.amount, move.amount_residual) > 0:
            raise UserError(_("The amount is more than what is due on %s.", move.name))
        move._apply_advance(payment, self.amount)
        return {"type": "ir.actions.act_window_close"}
