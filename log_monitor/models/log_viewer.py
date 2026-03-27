# -*- coding: utf-8 -*-
from odoo import fields, models


class LogViewer(models.TransientModel):
    _name = 'log.viewer'
    _description = 'Log File Viewer'

    content = fields.Html(string='Log File Content', readonly=True, sanitize=False)
    line_count = fields.Integer(string='Lines shown', readonly=True)
    log_path = fields.Char(string='Log File', readonly=True)
