from odoo import models, fields, api


class ModuleUpgradeHistory(models.Model):
    _name = 'module.upgrade.history'
    _description = 'Module Upgrade History'
    _order = 'upgrade_date desc, id desc'
    _rec_name = 'module_id'

    module_id = fields.Many2one(
        'ir.module.module',
        string='Module',
        required=True,
        ondelete='cascade',
        index=True,
        help='The module that was upgraded'
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
        store=True,
        help='Human-readable name of the module'
    )

    from_version = fields.Char(
        string='From Version',
        required=True,
        help='Version before the upgrade'
    )

    to_version = fields.Char(
        string='To Version',
        required=True,
        help='Version after the upgrade'
    )

    upgrade_date = fields.Datetime(
        string='Upgrade Date',
        required=True,
        default=fields.Datetime.now,
        index=True,
        help='Date and time when the upgrade was performed'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Upgraded By',
        default=lambda self: self.env.user,
        index=True,
        help='User who performed the upgrade'
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
        help='Status of the upgrade operation'
    )

    upgrade_method = fields.Selection([
        ('ui', 'UI (Manual)'),
        ('cli', 'Command Line'),
        ('automated', 'Automated'),
        ('unknown', 'Unknown'),
    ],
        string='Upgrade Method',
        default='unknown',
        help='How the upgrade was initiated'
    )

    notes = fields.Text(
        string='Notes',
        help='Optional notes about this upgrade'
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
            name = f"{record.module_display_name or record.module_name} ({record.from_version} → {record.to_version})"
            result.append((record.id, name))
        return result
