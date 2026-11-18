from odoo import Command, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    advance_payment_id = fields.Many2one(
        "account.payment",
        string="Applied Advance",
        copy=False,
        readonly=True,
        index="btree_not_null",
        help="The advance this entry moved onto an invoice or bill.",
    )
    has_open_advances = fields.Boolean(compute="_compute_has_open_advances")

    def _open_advances_domain(self):
        self.ensure_one()
        return [
            ("is_advance", "=", True),
            ("advance_residual", ">", 0),
            ("company_id", "=", self.company_id.id),
            ("partner_id", "child_of", self.commercial_partner_id.id),
            (
                "partner_type",
                "=",
                "customer" if self.move_type == "out_invoice" else "supplier",
            ),
        ]

    def _compute_has_open_advances(self):
        Payment = self.env["account.payment"]
        for move in self:
            move.has_open_advances = (
                move.move_type in ("out_invoice", "in_invoice")
                and move.state == "posted"
                and move.payment_state in ("not_paid", "partial")
                and bool(Payment.search_count(move._open_advances_domain(), limit=1))
            )

    def action_apply_advance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Apply Advance"),
            "res_model": "account.advance.apply",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _apply_advance(self, payment, amount):
        """Move ``amount`` of ``payment`` from its advance account onto this invoice or
        bill with one journal entry, and reconcile it with both."""
        self.ensure_one()
        if self.currency_id != self.company_currency_id:
            raise UserError(
                self.env._("Only invoices in the company currency can take advances.")
            )
        term_lines = self.line_ids.filtered(
            lambda line: (
                line.account_id.account_type
                in ("asset_receivable", "liability_payable")
                and not line.reconciled
            )
        )
        advance_lines = payment._advance_lines().filtered(
            lambda line: not line.reconciled
        )
        if not term_lines or not advance_lines:
            raise UserError(self.env._("Nothing is left to apply."))
        journal = self.env["account.journal"].search(
            [
                *self.env["account.journal"]._check_company_domain(self.company_id),
                ("type", "=", "general"),
            ],
            limit=1,
        )
        if not journal:
            raise UserError(
                self.env._("Create a miscellaneous journal to apply advances.")
            )
        # an invoice's receivable is credited, a bill's payable debited
        sign = -1 if self.move_type == "out_invoice" else 1
        label = self.env._(
            "Advance %(advance)s on %(move)s", advance=payment.name, move=self.name
        )
        partner = self.commercial_partner_id
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": fields.Date.context_today(self),
                "ref": label,
                "advance_payment_id": payment.id,
                "line_ids": [
                    Command.create(
                        {
                            "name": label,
                            "account_id": term_lines[0].account_id.id,
                            "partner_id": partner.id,
                            "balance": sign * amount,
                        }
                    ),
                    Command.create(
                        {
                            "name": label,
                            "account_id": advance_lines[0].account_id.id,
                            "partner_id": partner.id,
                            "balance": -sign * amount,
                        }
                    ),
                ],
            }
        )
        entry.action_post()
        for lines in (term_lines, advance_lines):
            new_line = entry.line_ids.filtered(
                lambda line, account=lines[0].account_id: line.account_id == account
            )
            (new_line + lines).reconcile()
        return entry

    def action_undo_advance(self):
        """Give the amount back to the advance: unreconcile and reverse the entry."""
        for move in self:
            if not move.advance_payment_id or move.state != "posted":
                raise UserError(
                    self.env._("%s is not an applied advance.", move.display_name)
                )
            move._reverse_moves(
                [
                    {
                        "ref": self.env._("Undo: %s", move.ref),
                        "date": fields.Date.context_today(move),
                    }
                ],
                cancel=True,
            )
