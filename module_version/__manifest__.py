{
    'name': 'Module Version',
    'version': '17.0.4.2.0',
    'category': 'Extra Tools',
    'summary': 'Display module version, track lifecycle history, and check for App Store updates',
    'description': """
Module Version
====================
This module displays version information, tracks complete module lifecycle history,
and checks for updates available in the Odoo App Store.

Key Features:
-------------
* Version Display: Shows current installed version for all installed modules
* Upgrade Detection: Displays upgrade available indicator with version comparison
* Automatic Detection: Compares disk version (manifest) vs installed version (database)
* Complete Module History: Audit trail of installations, upgrades, and uninstallations
* Track operation details: versions, timestamps, users, operation types
* Filter and search by operation type (Install/Upgrade/Uninstall)
* App Store Update Check: Check for newer versions available in Odoo App Store
* Modal Display: View available updates in a convenient popup window

Help for administrators:
- Track when modules were installed, upgraded, or removed
- See who performed each operation
- View complete lifecycle history per module
- Identify patterns and troubleshoot issues
- Check for available updates from the Odoo App Store
    """,
    'author': 'Paulius Gaizauskas',
    'maintainer': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'email': 'paulius.gaizauskas@gmail.com',
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'support': 'paulius.gaizauskas@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/module_upgrade_history_views.xml',
        'views/ir_module_module_views.xml',
        'views/ir_module_update_info_views.xml',
        'views/res_config_settings_view.xml',
        'views/ir_cron_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'module_version/static/src/css/styles.css',
        ],
    },
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
