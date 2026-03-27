# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _update_last_login(self):
        super()._update_last_login()
        try:
            ip = request.httprequest.environ.get('REMOTE_ADDR', 'n/a') if request else 'n/a'
            ua = ''
            if request:
                ua = (request.httprequest.user_agent.string or '')[:512]
            self.env['user.session.log'].sudo().create({
                'user_id': self.id,
                'login_time': fields.Datetime.now(),
                'ip_address': ip,
                'user_agent': ua,
            })
        except Exception:
            _logger.exception(
                'user_activity_monitor: failed to create session log for user %s', self.id
            )
