# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime

from odoo import fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

LOGIN_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\d+\s+INFO\s+\S+\s+'
    r'odoo\.addons\.base\.models\.res_users:\s+'
    r'Login successful for db:\S+ login:(\S+) from (\S+)'
)
DATETIME_FMT = '%Y-%m-%d %H:%M:%S'
ALLOWED_PATH_PREFIX = '/opt/odoo/'


class LogImportWizard(models.TransientModel):
    _name = 'user.activity.log.import.wizard'
    _description = 'Import Sessions from Log File'

    log_path = fields.Char(
        string='Log File Path',
        default='/opt/odoo/odoo17/conf/odoo-systemd.log',
        required=True,
    )
    import_count = fields.Integer(string='Imported', readonly=True)
    skipped_count = fields.Integer(string='Skipped (duplicates)', readonly=True)
    summary = fields.Text(string='Summary', readonly=True)
    state = fields.Selection([('draft', 'Ready'), ('done', 'Done')], default='draft')

    def action_import(self):
        self.ensure_one()

        # Security: restrict to allowed path prefix
        if not self.log_path.startswith(ALLOWED_PATH_PREFIX):
            raise UserError(
                f'Log file path must be under {ALLOWED_PATH_PREFIX}. '
                f'Got: {self.log_path}'
            )
        if not os.path.isfile(self.log_path):
            raise UserError(f'File not found: {self.log_path}')

        # Build login → user_id map
        users = self.env['res.users'].sudo().search_read(
            [('active', 'in', [True, False])], ['id', 'login']
        )
        login_map = {u['login']: u['id'] for u in users}

        # Load existing (user_id, login_time) pairs to skip duplicates
        existing = self.env['user.session.log'].sudo().search_read(
            [], ['user_id', 'login_time']
        )
        existing_keys = {(r['user_id'][0], r['login_time']) for r in existing}

        records_to_create = []
        skipped = 0
        unknown_logins = set()

        with open(self.log_path, 'r', errors='replace') as f:
            for line in f:
                m = LOGIN_RE.match(line.strip())
                if not m:
                    continue
                ts_str, login, ip = m.group(1), m.group(2), m.group(3)
                try:
                    login_dt = datetime.strptime(ts_str, DATETIME_FMT)
                except ValueError:
                    continue

                user_id = login_map.get(login)
                if not user_id:
                    unknown_logins.add(login)
                    continue

                key = (user_id, login_dt)
                if key in existing_keys:
                    skipped += 1
                    continue

                records_to_create.append({
                    'user_id': user_id,
                    'login_time': login_dt,
                    'ip_address': ip,
                    'timed_out': True,
                    'user_agent': 'imported from log file',
                })
                existing_keys.add(key)

        if records_to_create:
            self.env['user.session.log'].sudo().create(records_to_create)

        created = len(records_to_create)
        summary_lines = [
            f'Created: {created} session records',
            f'Skipped (duplicates): {skipped}',
        ]
        if unknown_logins:
            summary_lines.append(
                f'Unknown logins (no matching user): {", ".join(sorted(unknown_logins))}'
            )

        self.write({
            'import_count': created,
            'skipped_count': skipped,
            'summary': '\n'.join(summary_lines),
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
