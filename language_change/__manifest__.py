# -*- coding: utf-8 -*-
{
    'name': 'Quick Language Switcher',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Fast language switching from the Odoo interface',
    'description': """
        This module adds a language selector dropdown in the Odoo navbar
        allowing users to switch between installed languages with a single click.
    """,
    'author': 'Paulius11',
    "website": "https://github.com/Paulius11/language_change",
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
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}