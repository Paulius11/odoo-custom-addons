{
    'name': 'User Activity Monitor',
    'version': '17.0.1.0.1',
    'category': 'Technical',
    'summary': 'Track user login sessions and detect unusual activity patterns',
    'author': 'Paulius Gaizauskas',
    'license': 'AGPL-3',
    'depends': ['base', 'web', 'bus'],
    'data': [
        'security/ir.model.access.csv',
        'security/user_activity_monitor_security.xml',
        'data/ir_cron.xml',
        'views/user_session_log_views.xml',
        'wizards/log_import_wizard.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
}
