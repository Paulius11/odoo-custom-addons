# -*- coding: utf-8 -*-
import os
import time
import logging
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_FALLBACK_LOG_PATH = '/opt/odoo/odoo17/conf/odoo-systemd.log'


class LogMonitorConfig(models.Model):
    """Operational state only — settings live in res.config.settings."""
    _name = 'log.monitor.config'
    _description = 'Log Monitor State'

    last_offset = fields.Integer(default=0)
    last_run = fields.Datetime(string='Last Run', readonly=True)

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @api.model
    def _get_config(self):
        cfg = self.search([], limit=1)
        if not cfg:
            cfg = self.create({})
        return cfg

    # ------------------------------------------------------------------
    # Read settings from ir.config_parameter
    # ------------------------------------------------------------------

    def _get_param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(key) or default

    def _get_log_path(self):
        from odoo.tools import config as odoo_config
        return (
            os.environ.get('ODOO_LOG_FILE')
            or odoo_config.get('logfile')
            or self._get_param('log_monitor.file_path')
            or _FALLBACK_LOG_PATH
        )

    def _get_levels(self):
        levels = ['CRITICAL']
        if self._get_param('log_monitor.capture_errors', 'True') not in ('False', '0', ''):
            levels.append('ERROR')
        if self._get_param('log_monitor.capture_warnings', 'True') not in ('False', '0', ''):
            levels.append('WARNING')
        return tuple(levels)

    def _get_retention_days(self):
        try:
            return int(self._get_param('log_monitor.retention_days', '7'))
        except ValueError:
            return 7

    def _get_view_lines(self):
        try:
            return max(1, int(self._get_param('log_monitor.view_lines', '500')))
        except ValueError:
            return 500

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------

    @api.model
    def run_watch(self):
        from .log_file_parser import LogFileParser

        t0 = time.monotonic()
        cfg = self._get_config()
        log_path = cfg._get_log_path()
        levels = cfg._get_levels()

        lines, new_offset = LogFileParser.read_new_lines(log_path, cfg.last_offset)
        events = LogFileParser.parse_events(lines, level_filter=levels)

        new_events = []
        for ev in events:
            existing = self.env['log.event'].search(
                [('dedup_key', '=', ev['dedup_key'])], limit=1
            )
            ts = datetime.strptime(ev['timestamp_str'], '%Y-%m-%d %H:%M:%S,%f')
            if existing:
                existing.write({'count': existing.count + 1, 'last_seen': ts})
            else:
                self.env['log.event'].create({
                    'dedup_key': ev['dedup_key'],
                    'level': ev['level'],
                    'db_name': ev['db_name'],
                    'module': ev['module'],
                    'message': ev['message'],
                    'first_seen': ts,
                    'last_seen': ts,
                })
                new_events.append(ev)

        self.env['log.event']._purge_old(days=cfg._get_retention_days())

        alert_email = cfg._get_param('log_monitor.alert_email')
        alert_on_error = cfg._get_param('log_monitor.alert_on_error', 'True') not in ('False', '0', '')
        if new_events and alert_email and alert_on_error:
            to_alert = [e for e in new_events if e['level'] == 'ERROR']
            if to_alert:
                cfg._send_alert_email(to_alert, alert_email)

        cfg.write({'last_offset': new_offset, 'last_run': fields.Datetime.now()})
        _logger.info(
            'log_monitor: scanned %d lines, %d new events in %.1fs',
            len(lines), len(new_events), time.monotonic() - t0,
        )

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    def _send_alert_email(self, events, alert_email):
        lines = ['[{}] {} — {}'.format(e['level'], e['module'], e['message']) for e in events[:20]]
        subject = 'Odoo Log Alert: {} new error(s)'.format(len(events))
        try:
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': '<pre style="font-family:monospace">{}</pre>'.format('\n'.join(lines)),
                'email_to': alert_email,
                'auto_delete': True,
            }).send()
            _logger.info('log_monitor: alert email sent to %s', alert_email)
        except Exception:
            _logger.exception('log_monitor: failed to send alert email')

    # ------------------------------------------------------------------
    # Log viewer
    # ------------------------------------------------------------------

    _LOG_COLORS = {
        'CRITICAL': ('#e5534b', True),
        'ERROR':    ('#e5534b', True),
        'WARNING':  ('#d4a72c', False),
    }

    def _colorize_log_lines(self, lines):
        import re
        import html as html_mod
        level_re = re.compile(r'\s(CRITICAL|ERROR|WARNING|INFO)\s')
        result = []
        for line in lines:
            m = level_re.search(line)
            level = m.group(1) if m else None
            if level == 'INFO':
                continue
            escaped = html_mod.escape(line.rstrip('\n'))
            if level and level in self._LOG_COLORS:
                color, bold = self._LOG_COLORS[level]
                bg = 'background:#fff0f0;' if level in ('ERROR', 'CRITICAL') else 'background:#fffbe6;'
                style = 'color:{};{}{}'.format(color, 'font-weight:bold;' if bold else '', bg)
                result.append('<span style="display:block;{}">{}</span>'.format(style, escaped))
            else:
                result.append('<span style="color:#555555">{}</span>'.format(escaped))
        return '<pre style="font-family:monospace;font-size:12px;margin:0;line-height:1.5">' + '\n'.join(result) + '</pre>'

    def action_view_log(self):
        path = self._get_log_path()
        n = self._get_view_lines()
        try:
            with open(path, 'r', errors='replace') as f:
                lines = f.readlines()
            tail_lines = lines[-n:]
            content = self._colorize_log_lines(tail_lines)
            shown = len(tail_lines)
        except (OSError, IOError) as e:
            content = '<pre>Cannot read log file: {}</pre>'.format(e)
            shown = 0
        viewer = self.env['log.viewer'].create({
            'content': content,
            'line_count': shown,
            'log_path': path,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Log File',
            'res_model': 'log.viewer',
            'res_id': viewer.id,
            'view_mode': 'form',
            'target': 'new',
        }
