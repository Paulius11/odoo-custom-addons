# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    log_monitor_file_path = fields.Char(
        string='Log File Path',
        config_parameter='log_monitor.file_path',
    )
    log_monitor_capture_errors = fields.Boolean(
        string='Capture ERROR events',
        config_parameter='log_monitor.capture_errors',
        default=True,
    )
    log_monitor_capture_warnings = fields.Boolean(
        string='Capture WARNING events',
        config_parameter='log_monitor.capture_warnings',
        default=True,
    )
    log_monitor_retention_days = fields.Integer(
        string='Retention (days)',
        config_parameter='log_monitor.retention_days',
        default=7,
    )
    log_monitor_view_lines = fields.Integer(
        string='Lines to show in viewer',
        config_parameter='log_monitor.view_lines',
        default=500,
    )
    log_monitor_alert_email = fields.Char(
        string='Alert Email(s)',
        config_parameter='log_monitor.alert_email',
        help='Comma-separated addresses. Leave blank to disable.',
    )
    log_monitor_alert_on_error = fields.Boolean(
        string='Email on ERROR',
        config_parameter='log_monitor.alert_on_error',
        default=True,
    )
