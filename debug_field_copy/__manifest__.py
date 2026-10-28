# -*- coding: utf-8 -*-
{
    'name': 'Debug Field Copy',
    'version': '17.0.1.1.2',
    'category': 'Technical',
    'summary': 'Copy field names from debug tooltip',
    'author': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'images': ['static/description/banner.png'],
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'debug_field_copy/static/src/css/field_tooltip.css',
            'debug_field_copy/static/src/xml/field_tooltip.xml',
            'debug_field_copy/static/src/js/popover_controller_guard.js',
            'debug_field_copy/static/src/js/field_tooltip_extension.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
