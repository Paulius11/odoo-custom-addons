from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TranslationChangeSet(models.Model):
    """One Apply or Revert: the history entry that can be undone as a whole."""

    _name = "translation.change.set"
    _description = "Translation Change Set"
    _order = "id desc"

    name = fields.Char(required=True, readonly=True)
    operation = fields.Selection(
        [
            ("apply", "Apply"),
            ("revert_term", "Revert terms"),
            ("revert_set", "Revert change set"),
            ("revert_all", "Revert everything"),
        ],
        required=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users", "By", default=lambda self: self.env.user, readonly=True
    )
    line_ids = fields.One2many("translation.change", "set_id", readonly=True)
    line_count = fields.Integer(compute="_compute_line_count")
    reverted_by_id = fields.Many2one("translation.change.set", readonly=True)

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.model
    def _log(self, operation, changes, name):
        """``changes``: [(override, old_value, new_value)]; False = Odoo's own."""
        # sudo: history is written here only, so its revert can trust it
        return (
            self.sudo()
            .create(
                {
                    "name": name,
                    "operation": operation,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "override_id": rec.id,
                                "old_value": old or False,
                                "new_value": new or False,
                            },
                        )
                        for rec, old, new in changes
                    ],
                }
            )
            .sudo(False)
        )

    def action_revert(self):
        """Undo this set: each term gets back the value it had before it.

        A term changed again by a later set is left alone and reported.
        """
        self.ensure_one()
        if self.reverted_by_id:
            raise UserError(_("This change set was already reverted."))
        changes, skipped = [], []
        for line in self.line_ids:
            rec = line.override_id
            if (rec.value or False) != (line.new_value or False):
                skipped.append(rec.source[:40])
                continue
            changes.append((rec, rec.value, line.old_value))
        for rec, _old, new in changes:
            rec.sudo().write({"value": new or False})
        Override = self.env["translation.override"]
        Override.browse([rec.id for rec, _o, _n in changes])._push_live()
        undo = self._log("revert_set", changes, _("Reverted: %s", self.name))
        self.sudo().reverted_by_id = undo
        message = _("%s term(s) restored.", len(changes))
        if skipped:
            message += " " + _(
                "Left alone, changed again later: %s", ", ".join(skipped)
            )
        return Override._notify(
            message, "warning" if skipped else "success", reload=bool(changes)
        )


class TranslationChange(models.Model):
    """One term inside a change set: its value before and after."""

    _name = "translation.change"
    _description = "Translation Change Line"
    _order = "id"

    set_id = fields.Many2one(
        "translation.change.set", required=True, ondelete="cascade", index=True
    )
    override_id = fields.Many2one(
        "translation.override", required=True, ondelete="cascade", index=True
    )
    lang = fields.Selection(related="override_id.lang")
    source = fields.Text(related="override_id.source")
    location = fields.Char(related="override_id.location")
    old_value = fields.Text("Before", help="Empty: Odoo's own translation.")
    new_value = fields.Text("After", help="Empty: Odoo's own translation.")
    date = fields.Datetime(related="set_id.create_date", string="When")
    user_id = fields.Many2one(related="set_id.user_id")
