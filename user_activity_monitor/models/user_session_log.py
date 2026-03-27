# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class UserSessionLog(models.Model):
    _name = 'user.session.log'
    _description = 'User Session Log'
    _order = 'login_time desc, id desc'
    _log_access = False

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='restrict',
        index=True,
    )
    login_time = fields.Datetime(
        string='Login Time',
        required=True,
        index=True,
    )
    logout_time = fields.Datetime(
        string='Logout Time',
        index=True,
    )
    duration = fields.Float(
        string='Duration (h)',
        compute='_compute_duration',
        store=True,
        digits=(10, 2),
    )
    ip_address = fields.Char(
        string='IP Address',
        index=True,
    )
    user_agent = fields.Char(
        string='User Agent',
    )
    timed_out = fields.Boolean(
        string='Timed Out',
        default=False,
        help='True if session was closed by the expiry cron (no explicit logout)',
    )
    login_hour = fields.Integer(
        string='Login Hour',
        compute='_compute_login_hour',
        store=True,
        index=True,
        help='Hour of day (0-23, UTC) when the session started',
    )

    @api.depends('login_time', 'logout_time')
    def _compute_duration(self):
        for rec in self:
            if rec.login_time and rec.logout_time:
                delta = (rec.logout_time - rec.login_time).total_seconds()
                rec.duration = max(0.0, delta / 3600)
            else:
                rec.duration = 0.0

    @api.depends('login_time')
    def _compute_login_hour(self):
        for rec in self:
            rec.login_hour = rec.login_time.hour if rec.login_time else 0

    def _mark_expired_sessions(self):
        """Called by hourly cron. Closes sessions with no explicit logout after 12 hours."""
        cutoff = fields.Datetime.now() - timedelta(hours=12)
        stale = self.search([
            ('logout_time', '=', False),
            ('login_time', '<', cutoff),
        ])
        if stale:
            stale.write({
                'logout_time': fields.Datetime.now(),
                'timed_out': True,
            })
            _logger.info('user_activity_monitor: expired %d stale sessions', len(stale))
