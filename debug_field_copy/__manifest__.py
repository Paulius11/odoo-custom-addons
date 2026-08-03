# -*- coding: utf-8 -*-
{
    'name': 'Debug Field Copy',
    'version': '17.0.1.1.1',
    'category': 'Technical',
    'summary': 'Copy field names from debug tooltip',
    'description': """
Debug Field Copy
================

This module enhances the developer mode field tooltip by adding:
- Copy buttons next to each field property (Field name, Model, Type, etc.)
- Pin button to keep the tooltip open while moving the mouse

This makes it easy to copy field technical names for development purposes.
    """,
    'author': 'Custom',
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
