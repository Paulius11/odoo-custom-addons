from odoo import api, fields, models
from odoo.exceptions import UserError


class MailLostRoute(models.TransientModel):
    _name = "mail.lost.route"
    _description = "Route Lost Emails"

    lost_ids = fields.Many2many("mail.lost", string="Emails", required=True)
    mode = fields.Selection(
        [("existing", "Add to a record"), ("new", "Create a record")],
        default="existing",
        required=True,
    )
    record_ref = fields.Reference(selection="_selection_target_model", string="Record")
    model = fields.Selection(selection="_selection_create_model", string="Create a")

    @api.model
    def _selection_target_model(self):
        return self.env["mail.lost"]._selection_target_model()

    @api.model
    def _selection_create_model(self):
        # an email cannot give the login a user needs
        targets = self._selection_target_model()
        return [target for target in targets if target[0] != "res.users"]

    def action_confirm(self):
        self.ensure_one()
        if self.mode == "existing":
            record = self.record_ref
            if not record:
                raise UserError(self.env._("Pick the record the emails belong to."))
            # routing posts as superuser, so the user must be allowed to post there
            record.check_access(record._mail_post_access)
            model, res_id = record._name, record.id
        else:
            if not self.model:
                raise UserError(self.env._("Pick what to create from the emails."))
            self.env[self.model].check_access("create")
            model, res_id = self.model, False
        targets = [lost._route_to(model, res_id) for lost in self.lost_ids]
        if len(set(targets)) != 1:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": model,
            "res_id": targets[0],
            "view_mode": "form",
            "target": "current",
        }
