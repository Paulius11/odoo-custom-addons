# -*- coding: utf-8 -*-
{
    'name': 'Quick Language Switcher',
    'version': '17.0.1.0.1',
    'category': 'Tools',
    'author': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'summary': 'Fast language switching from the Odoo interface',
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