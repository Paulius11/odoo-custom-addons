from odoo import fields, models


class UserMessageWizard(models.TransientModel):
    _name = 'elics.user.message.wizard'
    _description = 'Send Message to User'

    user_id = fields.Many2one('res.users', string='Recipient', required=True)
    message = fields.Html(
        string='Message',
        sanitize=True,
        strip_style=False,
        required=True,
    )

    def action_send(self):
        self.ensure_one()
        self.user_id._send_odoobot_dm(self.message)
        return {'type': 'ir.actions.act_window_close'}
