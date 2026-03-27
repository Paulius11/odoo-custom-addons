# -*- coding: utf-8 -*-
from . import models


def post_migrate(cr, registry):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    records = env['log.monitor.config'].search([], order='id asc')
    if len(records) > 1:
        records[1:].with_context(skip_unlink_check=True).unlink()
