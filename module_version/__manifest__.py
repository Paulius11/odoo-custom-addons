{
    'name': 'Module Version',
    'version': '17.0.1.0.2',
    'category': 'Extra Tools',
    'summary': 'Display module version and upgrade status  in Apps view',
    'description': """
Module Version
====================
This module displays version information as colored on module cards in the Apps view.

Key Features:
-------------
* Version Display: Shows current installed version for all installed modules
* Upgrade Detection: Displays upgrade available indicator with version comparison
* Automatic Detection: Compares disk version (manifest) vs installed version (database)

Help for administrators quickly identify:
- Which modules are up to date 
- Which modules have updates available 
- Current version of each installed module
    """,
    'author': 'Paulius Gaizauskas',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
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
