# -*- coding: utf-8 -*-
{
    'name': 'Quick Language Switcher',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'author': 'Paulius Gaizauskas',
    'maintainer': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'email': 'paulius.gaizauskas@gmail.com',
    'summary': 'Fast language switching from the Odoo interface',
    'description': """
Quick Language Switcher
=======================
Switch between languages instantly with a convenient navbar dropdown - no need to go to preferences!

Key Features:
-------------
* Navbar Integration: Language selector directly in the Odoo navbar for instant access
* One-Click Switching: Change languages with a single click - no page navigation required
* All Languages: Access all installed and activated languages from the dropdown
* Instant Reload: Interface updates immediately after selection
* Universal Compatibility: Works on all Odoo screens and modules
* Zero Configuration: Ready to use immediately after installation

Perfect For:
------------
* Multi-language Organizations: Teams working across different language preferences
* International Teams: Quick switching for users who speak multiple languages
* Demonstrations: Easy language changes during client presentations
* Translation Testing: Quickly verify translations across languages

Technical Details:
-----------------
* Uses native Odoo language system
* Lightweight JavaScript implementation
* No database modifications required
* Compatible with all language packs

Installation:
Install the module and activate your desired languages in Settings > Translations > Languages.
The language switcher will appear automatically in the navbar.
    """,
    'depends': ['web', 'base'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'language_change/static/src/components/language_switcher/language_switcher.js',
            'language_change/static/src/components/language_switcher/language_switcher.xml',
            'language_change/static/src/components/language_switcher/language_switcher.scss',
            'language_change/static/src/services/language_service.js',
        ],
    },
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'support': 'paulius.gaizauskas@gmail.com',
}