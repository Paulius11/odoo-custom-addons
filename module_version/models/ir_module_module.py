import json
import requests
from datetime import datetime, timedelta

from odoo import _, models, fields, api
from odoo.tools.parse_version import parse_version
from odoo.addons.base.models.ir_module import assert_log_admin_access
from odoo.modules.module import get_module_path
from odoo.service.common import exp_version

try:
    from odoo.addons.base_import_module.models.ir_module import APPS_URL
except ImportError:
    APPS_URL = "https://apps.odoo.com"


def _parse_since(since_str):
    """Parse ISO datetime string; return epoch datetime on failure."""
    try:
        return datetime.fromisoformat(since_str)
    except Exception:
        return datetime.min


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

    last_operation_date = fields.Datetime(
        string='Last Operation Date',
        compute='_compute_last_operation_date',
        store=True,
        index=True,
    )

    module_path = fields.Char(
        string='Module Path',
        compute='_compute_module_path',
        store=False,
    )

    is_newly_added = fields.Boolean(
        string='Newly Added',
        compute='_compute_snapshot_flags',
        search='_search_is_newly_added',
        store=False,
        help='True if this module was installed for the first time within the last 30 days',
    )

    is_recently_upgraded = fields.Boolean(
        string='Recently Upgraded',
        compute='_compute_snapshot_flags',
        search='_search_is_recently_upgraded',
        store=False,
        help='True if this module was upgraded within the last 30 days',
    )

    @api.depends('upgrade_history_ids.upgrade_date')
    def _compute_last_operation_date(self):
        for module in self:
            history = module.upgrade_history_ids.sorted('upgrade_date', reverse=True)
            module.last_operation_date = history[0].upgrade_date if history else False

    @api.depends('name')
    def _compute_module_path(self):
        for module in self:
            module.module_path = get_module_path(module.name) or ''

    def _get_snapshot(self):
        """Return the stored module snapshot dict, or {} if not yet created."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'module_version.installed_snapshot', '{}'
        )
        try:
            return json.loads(raw)
        except Exception:
            return {}

    @api.depends('state', 'latest_version')
    def _compute_snapshot_flags(self):
        cutoff = datetime.utcnow() - timedelta(days=30)
        snapshot = self._get_snapshot()
        for module in self:
            if module.state != 'installed':
                module.is_newly_added = False
                module.is_recently_upgraded = False
                continue
            entry = snapshot.get(module.name)
            if not entry:
                module.is_newly_added = False
                module.is_recently_upgraded = False
                continue
            try:
                since = datetime.fromisoformat(entry['since'])
            except Exception:
                module.is_newly_added = False
                module.is_recently_upgraded = False
                continue
            recent = since >= cutoff
            module.is_newly_added = recent and entry.get('is_new', False)
            module.is_recently_upgraded = recent and bool(entry.get('upgraded_from'))

    def _search_is_newly_added(self, operator, value):
        cutoff = datetime.utcnow() - timedelta(days=30)
        snapshot = self._get_snapshot()
        newly_added = [
            name for name, entry in snapshot.items()
            if entry.get('is_new')
            and _parse_since(entry.get('since')) >= cutoff
        ]
        installed = self.search([('state', '=', 'installed'), ('name', 'in', newly_added)])
        ids = installed.ids
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', ids)]
        return [('id', 'not in', ids)]

    def _search_is_recently_upgraded(self, operator, value):
        cutoff = datetime.utcnow() - timedelta(days=30)
        snapshot = self._get_snapshot()
        upgraded = [
            name for name, entry in snapshot.items()
            if entry.get('upgraded_from')
            and _parse_since(entry.get('since')) >= cutoff
        ]
        installed = self.search([('state', '=', 'installed'), ('name', 'in', upgraded)])
        ids = installed.ids
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', ids)]
        return [('id', 'not in', ids)]

    def _update_module_snapshot(self):
        """Update snapshot entries for self after an install or upgrade."""
        ICP = self.env['ir.config_parameter'].sudo()
        snapshot = self._get_snapshot()
        now = datetime.utcnow().isoformat()
        for module in self:
            if module.state != 'installed':
                continue
            name = module.name
            new_ver = module.latest_version or ''
            existing = snapshot.get(name)
            if not existing:
                # First time seen — mark as new
                snapshot[name] = {'version': new_ver, 'since': now, 'is_new': True}
            elif existing.get('version') != new_ver:
                # Version changed — mark as upgraded
                snapshot[name] = {
                    'version': new_ver,
                    'since': now,
                    'is_new': False,
                    'upgraded_from': existing.get('version', ''),
                }
            # If version unchanged, leave entry as-is
        ICP.set_param('module_version.installed_snapshot', json.dumps(snapshot))

    def _sync_module_snapshot(self):
        """Compare all installed modules against snapshot; record new/upgraded entries.

        Called once per server start via _register_hook() to catch CLI installs/upgrades.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        snapshot = self._get_snapshot()
        if not snapshot:
            # Snapshot not yet initialised (module_version just installed via CLI without
            # post_init_hook running) — bootstrap it with all modules as pre-existing.
            modules = self.search([('state', '=', 'installed')])
            now = datetime.utcnow().isoformat()
            snapshot = {
                m.name: {'version': m.latest_version or '', 'since': now, 'is_new': False}
                for m in modules
            }
            ICP.set_param('module_version.installed_snapshot', json.dumps(snapshot))
            return

        modules = self.search([('state', '=', 'installed')])
        now = datetime.utcnow().isoformat()
        changed = False
        for module in modules:
            name = module.name
            new_ver = module.latest_version or ''
            existing = snapshot.get(name)
            if not existing:
                snapshot[name] = {'version': new_ver, 'since': now, 'is_new': True}
                changed = True
            elif existing.get('version') != new_ver:
                snapshot[name] = {
                    'version': new_ver,
                    'since': now,
                    'is_new': False,
                    'upgraded_from': existing.get('version', ''),
                }
                changed = True
        if changed:
            ICP.set_param('module_version.installed_snapshot', json.dumps(snapshot))

    # Class-level guard so _sync_module_snapshot runs only once per server process
    _snapshot_synced = False

    def _register_hook(self):
        res = super()._register_hook()
        if not IrModuleModule._snapshot_synced:
            IrModuleModule._snapshot_synced = True
            try:
                self._sync_module_snapshot()
            except Exception:
                pass
        return res

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
            "view_mode": "list",
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

    def _history_table_exists(self):
        """Return True if the module_upgrade_history table is present in the DB."""
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'module_upgrade_history'"
            )
            return bool(self.env.cr.fetchone())
        except Exception:
            return False

    def _detect_upgrade_method(self):
        try:
            from odoo.http import request
            return 'ui' if request else 'cli'
        except Exception:
            return 'cli'

    def _create_module_history_record(self, operation_type='upgrade', from_version=None,
                                       to_version=None, status='success', notes=None):
        """Create module history record for install/upgrade/uninstall operations."""
        self.ensure_one()
        if not self._history_table_exists():
            return False
        try:
            return self.env['module.upgrade.history'].sudo().create({
                'module_id': self.id,
                'operation_type': operation_type,
                'from_version': from_version or '',
                'to_version': to_version or '',
                'user_id': self.env.user.id,
                'upgrade_method': self._detect_upgrade_method(),
                'status': status,
                'notes': notes or '',
            })
        except Exception:
            return False

    def _resolve_pending_record(self, operation_type, from_version, to_version, status, notes=None):
        """Find an open pending history record and mark it resolved, or create a new one."""
        self.ensure_one()
        if not self._history_table_exists():
            return
        try:
            domain = [
                ('module_id', '=', self.id),
                ('operation_type', '=', operation_type),
                ('status', '=', 'pending'),
            ]
            if from_version:
                domain.append(('from_version', '=', from_version))
            pending = self.env['module.upgrade.history'].sudo().search(domain, limit=1)
            if pending:
                vals = {'status': status, 'upgrade_date': fields.Datetime.now()}
                if to_version is not None:
                    vals['to_version'] = to_version
                if notes:
                    vals['notes'] = notes
                pending.write(vals)
            else:
                self._create_module_history_record(
                    operation_type=operation_type,
                    from_version=from_version,
                    to_version=to_version or '',
                    status=status,
                    notes=notes,
                )
        except Exception:
            pass

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
        pre = {m.id: m.installed_version or '1.0' for m in self if m.state == 'installed'}
        result = super().button_upgrade()
        for module in self:
            if module.id in pre:
                module._create_module_history_record(
                    operation_type='upgrade',
                    from_version=pre[module.id],
                    to_version=module.latest_version or '1.0',
                    status='pending',
                )
        return result

    @assert_log_admin_access
    def button_immediate_upgrade(self):
        pre = {m.id: m.installed_version or '1.0' for m in self if m.state == 'installed'}
        try:
            result = super().button_immediate_upgrade()
            for module in self:
                if module.id in pre:
                    module._resolve_pending_record(
                        operation_type='upgrade',
                        from_version=pre[module.id],
                        to_version=module.latest_version or '1.0',
                        status='success',
                    )
            self._update_module_snapshot()
            return result
        except Exception as e:
            for module in self:
                if module.id in pre:
                    module._resolve_pending_record(
                        operation_type='upgrade',
                        from_version=pre[module.id],
                        to_version=module.latest_version or '1.0',
                        status='failed',
                        notes=f'Upgrade failed: {e}',
                    )
            raise

    @assert_log_admin_access
    def button_install(self):
        pre = {m.id: m.latest_version or '1.0' for m in self if m.state == 'uninstalled'}
        result = super().button_install()
        for module in self:
            if module.id in pre:
                module._create_module_history_record(
                    operation_type='install',
                    from_version='',
                    to_version=pre[module.id],
                    status='pending',
                )
        return result

    @assert_log_admin_access
    def button_immediate_install(self):
        pre = {m.id: m.latest_version or '1.0' for m in self if m.state == 'uninstalled'}
        try:
            result = super().button_immediate_install()
            for module in self:
                if module.id in pre:
                    module._resolve_pending_record(
                        operation_type='install',
                        from_version='',
                        to_version=module.latest_version or '1.0',
                        status='success',
                    )
            self._update_module_snapshot()
            return result
        except Exception as e:
            for module in self:
                if module.id in pre:
                    module._resolve_pending_record(
                        operation_type='install',
                        from_version='',
                        to_version=pre[module.id],
                        status='failed',
                        notes=f'Installation failed: {e}',
                    )
            raise

    @assert_log_admin_access
    def button_uninstall(self):
        pre = {
            m.id: m.installed_version or m.latest_version or '1.0'
            for m in self if m.state in ('installed', 'to upgrade')
        }
        result = super().button_uninstall()
        for module in self:
            if module.id in pre:
                module._create_module_history_record(
                    operation_type='uninstall',
                    from_version=pre[module.id],
                    to_version='',
                    status='pending',
                )
        return result

    @assert_log_admin_access
    def button_immediate_uninstall(self):
        pre = {
            m.id: m.installed_version or m.latest_version or '1.0'
            for m in self if m.state in ('installed', 'to upgrade')
        }
        try:
            result = super().button_immediate_uninstall()
            for module in self:
                if module.id in pre:
                    module._resolve_pending_record(
                        operation_type='uninstall',
                        from_version=pre[module.id],
                        to_version='',
                        status='success',
                    )
            return result
        except Exception as e:
            for module in self:
                if module.id in pre:
                    module._resolve_pending_record(
                        operation_type='uninstall',
                        from_version=pre[module.id],
                        to_version='',
                        status='failed',
                        notes=f'Uninstallation failed: {e}',
                    )
            raise
