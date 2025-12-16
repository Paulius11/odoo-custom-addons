{
    'name': 'Module Version',
    'version': '17.0.2.0.1',
    'category': 'Extra Tools',
    'summary': 'Display module version, upgrade status, and track upgrade history',
    'description': """
Module Version
====================
This module displays version information and tracks module upgrade history.

Key Features:
-------------
* Version Display: Shows current installed version for all installed modules
* Upgrade Detection: Displays upgrade available indicator with version comparison
* Automatic Detection: Compares disk version (manifest) vs installed version (database)
* Upgrade History: Complete audit trail of all module upgrades
* Track upgrade details: versions, timestamps, users, methods (UI/CLI)
* Filter and search upgrade history

Help for administrators quickly identify:
- Which modules are up to date
- Which modules have updates available
- Current version of each installed module
- Complete history of when modules were upgraded
    """,
    'author': 'Paulius Gaizauskas',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/module_upgrade_history_views.xml',
        'views/ir_module_module_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'module_version/static/src/css/module_version_badge.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
