# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_logout(cls):
        # request.env.uid is still available here:
        # Session.logout() clears session dict (line 1110) then calls _post_logout (line 1116),
        # but request.env was constructed earlier and still holds the original uid.
        uid = None
        try:
            if request and request.env and request.env.uid:
                uid = request.env.uid
        except Exception:
            _logger.debug('user_activity_monitor: could not read uid during logout')

        super()._post_logout()

        if uid:
            try:
                session_log = request.env['user.session.log'].sudo().search([
                    ('user_id', '=', uid),
                    ('logout_time', '=', False),
                ], order='login_time desc', limit=1)
                if session_log:
                    session_log.write({'logout_time': fields.Datetime.now()})
            except Exception:
                _logger.exception(
                    'user_activity_monitor: failed to close session log for uid %s', uid
                )
