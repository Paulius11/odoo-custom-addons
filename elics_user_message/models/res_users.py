from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    user_message = fields.Html(
        string='Send Message to User',
        sanitize=True,
        strip_style=False,
        help="Message to send as OdooBot DM to this user. Cleared after sending.",
    )
    user_message_enabled = fields.Boolean(
        string='Send Message',
        default=False,
        help="Check and save to send the message above as a chat DM to this user.",
    )

    def write(self, vals):
        result = super().write(vals)
        if vals.get('user_message_enabled'):
            for user in self:
                if user.user_message_enabled and user.user_message:
                    user._send_odoobot_dm(user.user_message)
            super(ResUsers, self).write({
                'user_message_enabled': False,
                'user_message': False,
            })
        return result

    def _send_odoobot_dm(self, body):
        odoobot = self.env.ref('base.partner_root')
        odoobot_user = odoobot.user_ids[:1]
        # channel_get appends env.user.partner_id automatically, so pass only the recipient
        # and run as OdooBot so the two participants are: OdooBot + recipient
        channel = self.env['discuss.channel'].with_user(odoobot_user).channel_get(
            partners_to=[self.partner_id.id],
            pin=True,
        )
        self.env['discuss.channel'].sudo().browse(channel['id']).message_post(
            body=body,
            message_type='comment',
            author_id=odoobot.id,
            subtype_xmlid='mail.mt_comment',
        )
