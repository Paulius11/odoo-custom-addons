from odoo import api, fields, models


class DebugLogEntry(models.Model):
    _name = "debug.logger.entry"
    _description = "Debug Logger Entry"
    # id, not create_date: entries of one transaction share the same create_date
    _order = "id desc"
    _rec_name = "display_name"

    name = fields.Char(string="Operation", required=True, index=True)
    model = fields.Char(required=True, index=True)
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    data = fields.Text(string="Operation Data")
    caller_info = fields.Char(
        string="Called From", help="File and line where the operation was called"
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("name", "model")
    def _compute_display_name(self):
        """Compute a meaningful display name for the log entry."""
        for record in self:
            record.display_name = f"{record.name} on {record.model}"

    @api.model
    def _cleanup(self, keep):
        """Delete all but the newest `keep` entries."""
        if keep > 0:
            self.search([], offset=keep).unlink()
