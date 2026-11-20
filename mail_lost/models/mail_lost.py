import email
import email.errors
import email.policy
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes

_logger = logging.getLogger(__name__)

# Technical models with a chatter that no email belongs to.
HIDDEN_PREFIXES = ("ir.", "iap.", "base.", "bus.")
HIDDEN_SUFFIXES = (".blacklist",)


class MailLost(models.Model):
    _name = "mail.lost"
    _description = "Lost Email"
    _inherit = "mail.thread"
    _order = "message_date desc, id desc"

    name = fields.Char("Subject", readonly=True)
    email_from = fields.Char("From", readonly=True)
    author_id = fields.Many2one("res.partner", "Sender", readonly=True)
    email_to = fields.Char("To", readonly=True)
    email_cc = fields.Char("Cc", readonly=True)
    message_date = fields.Datetime("Received", readonly=True)
    reason = fields.Char(
        readonly=True, help="Why Odoo could not route the email on its own."
    )
    raw_email = fields.Binary("Original Email", attachment=True, readonly=True)
    state = fields.Selection(
        [("new", "To Route"), ("routed", "Routed"), ("ignored", "Ignored")],
        default="new",
        required=True,
        readonly=True,
        tracking=True,
    )
    target_model = fields.Char(readonly=True)
    target_res_id = fields.Many2oneReference(
        "Target Record ID", model_field="target_model", readonly=True
    )
    target_ref = fields.Reference(
        selection="_selection_target_model",
        compute="_compute_target_ref",
        string="Routed To",
    )

    @api.model
    def _selection_target_model(self):
        """Every business model with a chatter, except this one."""
        models_ = (
            self.env["ir.model"]
            .sudo()
            .search(
                [
                    ("is_mail_thread", "=", True),
                    ("transient", "=", False),
                    ("model", "!=", self._name),
                ]
            )
        )
        return [
            (m.model, m.name)
            for m in models_
            if m.model in self.env
            and not self.env[m.model]._abstract
            and not m.model.startswith(HIDDEN_PREFIXES)
            and not m.model.endswith(HIDDEN_SUFFIXES)
        ]

    @api.depends("target_model", "target_res_id")
    def _compute_target_ref(self):
        for lost in self:
            ok = lost.target_model in self.env and lost.target_res_id
            lost.target_ref = (
                f"{lost.target_model},{lost.target_res_id}" if ok else False
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        managers = self.env.ref("mail_lost.group_mail_lost_manager").user_ids
        records.message_subscribe(partner_ids=managers.partner_id.ids)
        return records

    # ------------------------------------------------------------------ gateway

    @api.model
    def _lost_route(self, message, message_dict, reason=False):
        """Route for an email core could not place: a new lost email."""
        try:
            raw = message.as_bytes()
        except (ValueError, email.errors.MessageError):
            # A header the SMTP policy cannot fold; keep the email, lose the original.
            _logger.warning(
                "mail_lost: original of %s not kept", message_dict.get("message_id")
            )
            raw = False
        values = {
            "raw_email": raw and BinaryBytes(raw),
            "reason": reason,
        }
        route = (self._name, False, values, self.env.uid, None)
        # sets message_dict["author_id"] from the sender, as core does for its routes
        checked = self._routing_check_route(
            message, message_dict, route, raise_exception=False
        )
        return checked or route

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        values = dict(
            custom_values or {},
            name=msg_dict.get("subject") or self.env._("(no subject)"),
            email_from=msg_dict.get("email_from"),
            author_id=msg_dict.get("author_id"),
            email_to=msg_dict.get("to"),
            email_cc=msg_dict.get("cc"),
            message_date=msg_dict.get("date") or fields.Datetime.now(),
        )
        return super().message_new(msg_dict, custom_values=values)

    # ------------------------------------------------------------------ actions

    def action_route(self):
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Route Lost Emails"),
            "res_model": "mail.lost.route",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_lost_ids": self.filtered_domain([("state", "=", "new")]).ids
            },
        }

    def action_ignore(self):
        self.filtered_domain([("state", "=", "new")]).state = "ignored"

    def action_reopen(self):
        self.filtered_domain([("state", "=", "ignored")]).state = "new"

    def _route_to(self, model, res_id=False):
        """Feed the original email to core routing with a forced destination, as an
        alias would: core posts it with its attachments, sets the author and
        followers, and creates the record when ``res_id`` is empty."""
        self.ensure_one()
        if self.state != "new":
            raise UserError(
                self.env._("%s is not waiting to be routed.", self.display_name)
            )
        if not self.raw_email:
            raise UserError(
                self.env._(
                    "The original of %s was not kept; copy it by hand.",
                    self.display_name,
                )
            )
        thread = self.env["mail.thread"]
        message = email.message_from_bytes(
            self.raw_email.content, policy=email.policy.SMTP
        )
        msg_dict = thread.message_parse(message)
        msg_dict.pop("parent_id", None)  # a parent in another thread means nothing here
        try:
            route = thread._routing_check_route(
                message, msg_dict, (model, res_id, None, self.env.uid, None)
            )
        except ValueError as error:
            raise UserError(str(error)) from error
        res_id = thread._message_route_process(message, msg_dict, [route]).id
        self.write({"state": "routed", "target_model": model, "target_res_id": res_id})
        return res_id
