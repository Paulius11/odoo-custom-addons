import requests

from odoo import _, models, fields, api
from odoo.tools.parse_version import parse_version
from odoo.addons.base.models.ir_module import assert_log_admin_access
from odoo.modules.module import get_module_path
from odoo.service.common import exp_version

try:
    from odoo.addons.base_import_module.models.ir_module import APPS_URL
except ImportError:
    APPS_URL = "https://apps.odoo.com"


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

    module_path = fields.Char(
        string='Module Path',
        compute='_compute_module_path',
        store=False,
    )

    @api.depends('name')
    def _compute_module_path(self):
        for module in self:
            module.module_path = get_module_path(module.name) or ''

    def action_check_updates_ui(self):
        """Check for App Store updates and display results."""
        UpdateInfo = self.env["ir.module.update.info"]
        UpdateInfo.search([]).unlink()

        modules_to_update = self.env["ir.module.module"].get_modules_need_update()

        if not modules_to_update:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Module Updates"),
                    "message": _("All modules are up to date!"),
                    "type": "success",
                    "sticky": False,
                },
            }

        for name, info in modules_to_update.items():
            UpdateInfo.create({
                "name": name,
                "display_name": info.get("display_name", name),
                "installed_version": info.get("version_local_running", ""),
                "available_version": info.get("version_remote", ""),
            })

        return {
            "type": "ir.actions.act_window",
            "name": _("Available Module Updates"),
            "res_model": "ir.module.update.info",
            "view_mode": "tree",
            "target": "new",
        }

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

    def _create_module_history_record(self, operation_type='upgrade', from_version=None,
                                       to_version=None, status='success', notes=None):
        """Create module history record for install/upgrade/uninstall operations"""
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
                'operation_type': operation_type,
                'from_version': from_version or '',
                'to_version': to_version or '',
                'user_id': self.env.user.id,
                'upgrade_method': upgrade_method,
                'status': status,
                'notes': notes or '',
            })
        except Exception:
            # Silently fail if table doesn't exist or other issues
            return False

    # ===========================================
    # App Store Version Checking Methods
    # ===========================================

    def check_app_store_updates(self, modules):
        """Check for updates in the app store for the given modules.

        Args:
            modules (dict): A dictionary of installed modules.

        Returns:
            dict: Information about the modules on the odoo server.
            Example:
            {
                'module.name': {
                    'id': 123,  # module ID
                    'name': 'example_module',  # module name
                    'version_local_running': '1.0.0',  # local version
                    'version_local_downloaded': '1.0.0',  # downloaded version
                    'version_remote': '1.2.0',  # version available in odoo app store
                    'todo': 'to_update',  # Indicates that an update is needed
                },
            }
        """
        url = f"{APPS_URL}/apps/embed/update"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "modules": modules,
                "version": exp_version(),
            },
        }
        try:
            response = requests.Session().post(url, json=payload, timeout=30).json()
            return response.get("result", {})
        except Exception:
            return {}

    def get_modules_need_update(self):
        """Find installed modules and get a dictionary of modules that need an update.

        Returns:
            dict: Modules that need an update.
            Example:
            {
                'module.name': {
                    'id': 123,  # module ID on the odoo server
                    'name': 'example_module',  # module name
                    'version_local_running': '1.0.0',  # local version
                    'version_local_downloaded': '1.0.0',  # downloaded version
                    'version_remote': '1.2.0',  # version available in odoo app store
                    'todo': 'to_update',  # Indicates that an update is needed
                    'display_name': 'Example Module',  # display name
                },
            }
        """
        installed_modules = self.search_read(
            [("state", "=", "installed")],
            fields=[
                "name",
                "installed_version",
                "latest_version",
                "state",
                "display_name",
            ],
        )
        modules_dict = {record["name"]: record for record in installed_modules}

        modules_to_update_dict = self.check_app_store_updates(modules_dict)

        for module_name, module_info in modules_to_update_dict.items():
            installed_module_info = modules_dict.get(module_name, {})
            module_info["display_name"] = installed_module_info.get("display_name", "")
        return modules_to_update_dict

    # ===========================================
    # Module History Tracking Methods
    # ===========================================

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
                module._create_module_history_record(
                    operation_type='upgrade',
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
                            ('operation_type', '=', 'upgrade'),
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
                            module._create_module_history_record(
                                operation_type='upgrade',
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
                    module._create_module_history_record(
                        operation_type='upgrade',
                        from_version=pre_upgrade_versions[module.id],
                        to_version=module.latest_version or '1.0',
                        status='failed',
                        notes=f'Upgrade failed: {str(e)}'
                    )
            raise

    @assert_log_admin_access
    def button_install(self):
        """Override to track installation history"""
        # Capture modules being installed
        modules_to_install = {}
        for module in self:
            if module.state == 'uninstalled':
                modules_to_install[module.id] = module.latest_version or '1.0'

        # Call parent
        result = super().button_install()

        # Create history records with 'pending' status
        for module in self:
            if module.id in modules_to_install:
                module._create_module_history_record(
                    operation_type='install',
                    from_version='',
                    to_version=modules_to_install[module.id],
                    status='pending'
                )

        return result

    @assert_log_admin_access
    def button_immediate_install(self):
        """Override to track installation history with success/failure status"""
        # Capture modules being installed
        modules_to_install = {
            m.id: m.latest_version or '1.0'
            for m in self if m.state == 'uninstalled'
        }

        try:
            # Call parent method
            result = super().button_immediate_install()

            # Success: create/update history
            for module in self:
                if module.id in modules_to_install:
                    # Check if table exists
                    try:
                        self.env.cr.execute(
                            "SELECT 1 FROM information_schema.tables WHERE table_name = 'module_upgrade_history'"
                        )
                        if not self.env.cr.fetchone():
                            continue
                    except Exception:
                        continue

                    # Find pending record or create new one
                    try:
                        pending = self.env['module.upgrade.history'].sudo().search([
                            ('module_id', '=', module.id),
                            ('operation_type', '=', 'install'),
                            ('status', '=', 'pending')
                        ], limit=1)

                        to_version = module.latest_version or '1.0'

                        if pending:
                            pending.write({
                                'status': 'success',
                                'to_version': to_version,
                                'upgrade_date': fields.Datetime.now(),
                            })
                        else:
                            module._create_module_history_record(
                                operation_type='install',
                                from_version='',
                                to_version=to_version,
                                status='success'
                            )
                    except Exception:
                        pass

            return result

        except Exception as e:
            # Failed: record failure
            for module in self:
                if module.id in modules_to_install:
                    module._create_module_history_record(
                        operation_type='install',
                        from_version='',
                        to_version=modules_to_install[module.id],
                        status='failed',
                        notes=f'Installation failed: {str(e)}'
                    )
            raise

    @assert_log_admin_access
    def button_uninstall(self):
        """Override to track uninstallation history"""
        # Capture modules being uninstalled
        modules_to_uninstall = {}
        for module in self:
            if module.state in ('installed', 'to upgrade'):
                modules_to_uninstall[module.id] = module.installed_version or module.latest_version or '1.0'

        # Call parent
        result = super().button_uninstall()

        # Create history records with 'pending' status
        for module in self:
            if module.id in modules_to_uninstall:
                module._create_module_history_record(
                    operation_type='uninstall',
                    from_version=modules_to_uninstall[module.id],
                    to_version='',
                    status='pending'
                )

        return result

    @assert_log_admin_access
    def button_immediate_uninstall(self):
        """Override to track uninstallation history with success/failure status"""
        # Capture modules being uninstalled
        modules_to_uninstall = {
            m.id: m.installed_version or m.latest_version or '1.0'
            for m in self if m.state in ('installed', 'to upgrade')
        }

        try:
            # Call parent method
            result = super().button_immediate_uninstall()

            # Success: create/update history
            for module in self:
                if module.id in modules_to_uninstall:
                    # Check if table exists
                    try:
                        self.env.cr.execute(
                            "SELECT 1 FROM information_schema.tables WHERE table_name = 'module_upgrade_history'"
                        )
                        if not self.env.cr.fetchone():
                            continue
                    except Exception:
                        continue

                    # Find pending record or create new one
                    try:
                        pending = self.env['module.upgrade.history'].sudo().search([
                            ('module_id', '=', module.id),
                            ('operation_type', '=', 'uninstall'),
                            ('status', '=', 'pending')
                        ], limit=1)

                        if pending:
                            pending.write({
                                'status': 'success',
                                'upgrade_date': fields.Datetime.now(),
                            })
                        else:
                            module._create_module_history_record(
                                operation_type='uninstall',
                                from_version=modules_to_uninstall[module.id],
                                to_version='',
                                status='success'
                            )
                    except Exception:
                        pass

            return result

        except Exception as e:
            # Failed: record failure
            for module in self:
                if module.id in modules_to_uninstall:
                    module._create_module_history_record(
                        operation_type='uninstall',
                        from_version=modules_to_uninstall[module.id],
                        to_version='',
                        status='failed',
                        notes=f'Uninstallation failed: {str(e)}'
                    )
            raise
