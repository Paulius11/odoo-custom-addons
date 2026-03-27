# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import timedelta


class LogEvent(models.Model):
    _name = 'log.event'
    _description = 'Odoo Log Event'
    _order = 'last_seen desc, id desc'
    _log_access = False
    _sql_constraints = [
        ('dedup_key_uniq', 'UNIQUE(dedup_key)', 'A log event with this key already exists'),
    ]

    dedup_key = fields.Char(required=True, index=True, readonly=True)
    level = fields.Selection(
        [('ERROR', 'Error'), ('CRITICAL', 'Critical'), ('WARNING', 'Warning')],
        required=True,
        index=True,
    )
    db_name = fields.Char('Database', index=True, readonly=True)
    module = fields.Char(index=True, readonly=True)
    message = fields.Text(readonly=True)
    count = fields.Integer(default=1, readonly=True)
    first_seen = fields.Datetime(readonly=True)
    last_seen = fields.Datetime(index=True, readonly=True)

    def name_get(self):
        return [
            (r.id, '[{}] {}: {}'.format(r.level, r.module, (r.message or '')[:60]))
            for r in self
        ]

    @api.model
    def _purge_old(self, days=7):
        """Delete events not seen within `days` days. Called by the watch cron."""
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.search([('last_seen', '<', cutoff)])
        if old:
            _count = len(old)
            old.unlink()
            import logging
            logging.getLogger(__name__).info(
                'log_monitor: purged %d old log events (older than %d days)', _count, days
            )
