# -*- coding: utf-8 -*-
{
    'name': 'Log Monitor',
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'summary': 'Tail Odoo log file and surface ERROR/CRITICAL events with email alerts',
    'author': 'Paulius Gaizauskas',
    'license': 'AGPL-3',
    'depends': ['base', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/log_event_views.xml',
        'views/log_viewer_views.xml',
        'views/log_monitor_config_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_migrate': 'post_migrate',
}
