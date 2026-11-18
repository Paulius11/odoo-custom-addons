from odoo import api, models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _detect_write_to_catchall(self, msg_dict):
        # Core bounces an email written straight to the catchall; keep it as lost.
        return False

    @api.model
    def message_route(
        self, message, message_dict, model=None, thread_id=None, custom_values=None
    ):
        lost = self.env["mail.lost"]
        try:
            routes = super().message_route(
                message,
                message_dict,
                model=model,
                thread_id=thread_id,
                custom_values=custom_values,
            )
        except ValueError as error:
            # Core gives up here: fetchmail drops the email, the mailgate bounces it.
            return [lost._lost_route(message, message_dict, str(error))]
        # A reply to a lost email is a lost email of its own, so each can be routed.
        return [
            lost._lost_route(message, message_dict) if route[0] == lost._name else route
            for route in routes
        ]
