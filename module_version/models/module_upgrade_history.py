from odoo import models, fields, api


class ModuleUpgradeHistory(models.Model):
    _name = 'module.upgrade.history'
    _description = 'Module History'
    _order = 'upgrade_date desc, id desc'
    _rec_name = 'module_id'

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

    def name_get(self):
        """Custom name display for the record"""
        result = []
        for record in self:
            if record.operation_type == 'install':
                name = f"{record.module_display_name or record.module_name} (Installed {record.to_version})"
            elif record.operation_type == 'uninstall':
                name = f"{record.module_display_name or record.module_name} (Uninstalled {record.from_version})"
            else:  # upgrade or None (for backward compatibility)
                name = f"{record.module_display_name or record.module_name} ({record.from_version} → {record.to_version})"
            result.append((record.id, name))
        return result

    def init(self):
        """Set default operation_type for existing records"""
        # Update existing records that don't have operation_type set
        self.env.cr.execute("""
            UPDATE module_upgrade_history
            SET operation_type = 'upgrade'
            WHERE operation_type IS NULL
        """)
