from odoo import models, fields, api
from odoo.tools.parse_version import parse_version
from odoo.addons.base.models.ir_module import assert_log_admin_access


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    version_badge_text = fields.Char(
        string='Version Badge Text',
        compute='_compute_version_badge',
        store=False
    )

    version_badge_class = fields.Char(
        string='Version Badge CSS Class',
        compute='_compute_version_badge',
        store=False
    )

    has_version_upgrade = fields.Boolean(
        string='Has Version Upgrade',
        compute='_compute_version_badge',
        search='_search_has_version_upgrade',
        store=False
    )

    upgrade_history_ids = fields.One2many(
        'module.upgrade.history',
        'module_id',
        string='Upgrade History',
        help='History of all upgrades for this module'
    )

    upgrade_history_count = fields.Integer(
        string='Upgrades',
        compute='_compute_upgrade_history_count',
        help='Number of upgrade history records'
    )

    @api.depends('state', 'installed_version', 'latest_version')
    def _compute_version_badge(self):
        """
        Compute version badge display properties for installed modules.

        - version_badge_text: Display text showing current and/or upgrade version
        - version_badge_class: CSS class for badge styling (badge-uptodate or badge-upgrade)
        - has_version_upgrade: Boolean indicating if upgrade is available
        """
        for module in self:
            # Only compute for installed modules
            if module.state != 'installed':
                module.version_badge_text = ''
                module.version_badge_class = ''
                module.has_version_upgrade = False
                continue

            # Get versions with fallback to default
            installed_ver = module.installed_version or '1.0'
            latest_ver = module.latest_version or '1.0'

            try:
                # Compare versions using packaging.version.parse
                installed_parsed = parse_version(installed_ver)
                latest_parsed = parse_version(latest_ver)

                # Check if upgrade is available (disk version > installed version)
                if installed_parsed > latest_parsed:
                    # Upgrade available
                    module.version_badge_text = f'v{latest_ver} → v{installed_ver}'
                    module.version_badge_class = 'badge-upgrade'
                    module.has_version_upgrade = True
                else:
                    # Up to date
                    module.version_badge_text = f'v{latest_ver}'
                    module.version_badge_class = 'badge-uptodate'
                    module.has_version_upgrade = False

            except Exception:
                # Fallback in case of version parsing errors
                module.version_badge_text = f'v{latest_ver}'
                module.version_badge_class = 'badge-uptodate'
                module.has_version_upgrade = False

    def _search_has_version_upgrade(self, operator, value):
        """
        Search method for has_version_upgrade computed field.
        Returns domain to filter modules with upgrades available.
        """
        # Get all installed modules
        installed_modules = self.search([('state', '=', 'installed')])

        # Filter modules with version upgrades
        modules_with_upgrade = []
        for module in installed_modules:
            installed_ver = module.installed_version or '1.0'
            latest_ver = module.latest_version or '1.0'

            try:
                installed_parsed = parse_version(installed_ver)
                latest_parsed = parse_version(latest_ver)

                has_upgrade = installed_parsed > latest_parsed

                # Apply operator logic
                if operator == '=' and value == has_upgrade:
                    modules_with_upgrade.append(module.id)
                elif operator == '!=' and value != has_upgrade:
                    modules_with_upgrade.append(module.id)
            except Exception:
                # Skip modules with parsing errors
                pass

        return [('id', 'in', modules_with_upgrade)]

    @api.depends('upgrade_history_ids')
    def _compute_upgrade_history_count(self):
        """Compute the number of upgrade history records"""
        for module in self:
            module.upgrade_history_count = len(module.upgrade_history_ids)

    def _create_upgrade_history_record(self, from_version, to_version,
                                        status='success', notes=None):
        """Create upgrade history record for this module"""
        self.ensure_one()

        # Check if the upgrade history table exists using SQL
        # (it won't exist during the initial installation of module_version)
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'module_upgrade_history'"
            )
            if not self.env.cr.fetchone():
                return False
        except Exception:
            return False

        # Detect upgrade method (UI vs CLI)
        upgrade_method = 'unknown'
        try:
            from odoo.http import request
            if request:
                upgrade_method = 'ui'
            else:
                upgrade_method = 'cli'
        except:
            upgrade_method = 'cli'

        # Use sudo() to bypass access rights when creating audit records
        try:
            return self.env['module.upgrade.history'].sudo().create({
                'module_id': self.id,
                'from_version': from_version,
                'to_version': to_version,
                'user_id': self.env.user.id,
                'upgrade_method': upgrade_method,
                'status': status,
                'notes': notes or '',
            })
        except Exception:
            # Silently fail if table doesn't exist or other issues
            return False

    @assert_log_admin_access
    def button_upgrade(self):
        """Override to track upgrade history"""
        # Capture pre-upgrade state
        pre_upgrade_data = {}
        for module in self:
            if module.state == 'installed':
                pre_upgrade_data[module.id] = {
                    'from_version': module.installed_version or '1.0',
                    'to_version': module.latest_version or '1.0',
                }

        # Call parent
        result = super().button_upgrade()

        # Create history records with 'pending' status
        for module in self:
            if module.id in pre_upgrade_data:
                module._create_upgrade_history_record(
                    from_version=pre_upgrade_data[module.id]['from_version'],
                    to_version=pre_upgrade_data[module.id]['to_version'],
                    status='pending'
                )

        return result

    @assert_log_admin_access
    def button_immediate_upgrade(self):
        """Override to track upgrade history with success/failure status"""
        # Capture versions before upgrade
        pre_upgrade_versions = {
            m.id: m.installed_version or '1.0'
            for m in self if m.state == 'installed'
        }

        try:
            # Call parent method
            result = super().button_immediate_upgrade()

            # Success: create/update history
            for module in self:
                if module.id in pre_upgrade_versions:
                    # Check if table exists before searching
                    try:
                        self.env.cr.execute(
                            "SELECT 1 FROM information_schema.tables WHERE table_name = 'module_upgrade_history'"
                        )
                        if not self.env.cr.fetchone():
                            continue
                    except Exception:
                        continue

                    # Find pending record or create new one (use sudo for audit records)
                    try:
                        pending = self.env['module.upgrade.history'].sudo().search([
                            ('module_id', '=', module.id),
                            ('status', '=', 'pending'),
                            ('from_version', '=', pre_upgrade_versions[module.id])
                        ], limit=1)

                        to_version = module.latest_version or '1.0'

                        if pending:
                            pending.write({
                                'status': 'success',
                                'to_version': to_version,
                                'upgrade_date': fields.Datetime.now(),
                            })
                        else:
                            module._create_upgrade_history_record(
                                from_version=pre_upgrade_versions[module.id],
                                to_version=to_version,
                                status='success'
                            )
                    except Exception:
                        # Skip if any error occurs
                        pass

            return result

        except Exception as e:
            # Failed: record failure
            for module in self:
                if module.id in pre_upgrade_versions:
                    module._create_upgrade_history_record(
                        from_version=pre_upgrade_versions[module.id],
                        to_version=module.latest_version or '1.0',
                        status='failed',
                        notes=f'Upgrade failed: {str(e)}'
                    )
            raise
