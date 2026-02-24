from datetime import timedelta

from odoo import models, fields, api


class ModuleUpgradeHistory(models.Model):
    _name = 'module.upgrade.history'
    _description = 'Module History'
    _order = 'upgrade_date desc, id desc'

    module_id = fields.Many2one(
        'ir.module.module',
        string='Module',
        required=True,
        ondelete='cascade',
        index=True,
        help='The module on which the operation was performed'
    )

    module_name = fields.Char(
        string='Technical Name',
        related='module_id.name',
        store=True,
        index=True,
        help='Technical name of the module'
    )

    module_display_name = fields.Char(
        string='Module Name',
        related='module_id.shortdesc',
        help='Human-readable name of the module'
    )

    operation_type = fields.Selection([
        ('install', 'Install'),
        ('upgrade', 'Upgrade'),
        ('uninstall', 'Uninstall'),
    ],
        string='Operation Type',
        required=False,
        default='upgrade',
        index=True,
        help='Type of operation performed on the module'
    )

    from_version = fields.Char(
        string='From Version',
        help='Version before the operation (empty for install)'
    )

    to_version = fields.Char(
        string='To Version',
        help='Version after the operation (empty for uninstall)'
    )

    upgrade_date = fields.Datetime(
        string='Operation Date',
        required=True,
        default=fields.Datetime.now,
        index=True,
        help='Date and time when the operation was performed'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Performed By',
        default=lambda self: self.env.user,
        index=True,
        help='User who performed the operation'
    )

    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ],
        string='Status',
        required=True,
        default='success',
        index=True,
        help='Status of the operation'
    )

    upgrade_method = fields.Selection([
        ('ui', 'UI (Manual)'),
        ('cli', 'Command Line'),
        ('automated', 'Automated'),
        ('unknown', 'Unknown'),
    ],
        string='Method',
        default='unknown',
        help='How the operation was initiated'
    )

    notes = fields.Html(
        string='Notes',
        help='Optional notes about this operation. You can add formatted text, screenshots, and images.',
        sanitize=False
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to False to archive this record'
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=False,
    )

    @api.depends('operation_type', 'module_display_name', 'module_name', 'from_version', 'to_version')
    def _compute_display_name(self):
        for record in self:
            label = record.module_display_name or record.module_name
            if record.operation_type == 'install':
                record.display_name = f"{label} (Installed {record.to_version})"
            elif record.operation_type == 'uninstall':
                record.display_name = f"{label} (Uninstalled {record.from_version})"
            else:
                record.display_name = f"{label} ({record.from_version} → {record.to_version})"

    def action_gc_stale_pending(self):
        """Delete pending records older than 24 hours (called by scheduled action).

        A pending record is created when a user queues an operation via the UI
        but the operation is never applied (e.g. closes the dialog). These are
        safe to remove after a day because any real completion would have already
        resolved them to success/failed.
        """
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        stale = self.search([
            ('status', '=', 'pending'),
            ('upgrade_date', '<', cutoff),
        ])
        stale.unlink()

    def init(self):
        """Set default operation_type for existing records."""
        self.env.cr.execute("""
            UPDATE module_upgrade_history
            SET operation_type = 'upgrade'
            WHERE operation_type IS NULL
        """)
