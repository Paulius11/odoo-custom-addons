{
    'name': 'Module Version',
    'version': '17.0.3.0.2',
    'category': 'Extra Tools',
    'summary': 'Display module version and track complete module lifecycle history',
    'description': """
Module Version
====================
This module displays version information and tracks complete module lifecycle history.

Key Features:
-------------
* Version Display: Shows current installed version for all installed modules
* Upgrade Detection: Displays upgrade available indicator with version comparison
* Automatic Detection: Compares disk version (manifest) vs installed version (database)
* Complete Module History: Audit trail of installations, upgrades, and uninstallations
* Track operation details: versions, timestamps, users, operation types
* Filter and search by operation type (Install/Upgrade/Uninstall)

Help for administrators:
- Track when modules were installed, upgraded, or removed
- See who performed each operation
- View complete lifecycle history per module
- Identify patterns and troubleshoot issues
    """,
    'author': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/module_upgrade_history_views.xml',
        'views/ir_module_module_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'module_version/static/src/css/styles.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
