from odoo import models, fields, api
from odoo.tools.parse_version import parse_version


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
