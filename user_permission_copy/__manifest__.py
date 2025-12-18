{
    'name': 'User Permission Copy',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'summary': 'Copy user permissions from one user to another',
    'description': """
        This module allows administrators to copy all permissions 
        from the current user to a selected target user.
        The target user's existing permissions will be replaced.
    """,
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'wizard/user_permission_copy_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}