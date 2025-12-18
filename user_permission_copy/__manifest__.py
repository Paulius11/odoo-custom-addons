{
    'name': 'User Permission Copy',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'author': 'Paulius Gaizauskas',
    'maintainer': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'email': 'paulius.gaizauskas@gmail.com',
    'summary': 'Copy user permissions from one user to another',
    'description': """
User Permission Copy
====================
Streamline user onboarding by copying permissions from one user to another with a simple wizard interface.

Key Features:
-------------
* Quick Replication: Copy all permissions from a source user to target user(s)
* Wizard Interface: Easy-to-use guided process for permission copying
* Complete Copy: Transfers groups, access rights, and rule assignments
* Safety First: Confirmation dialog prevents accidental permission changes
* Multi-user Support: Copy to multiple users at once

Perfect For:
------------
* New Employee Onboarding: Quickly set up new users with same permissions as colleagues
* Role Standardization: Ensure users in the same role have identical permissions
* Permission Templates: Use existing users as templates for new hires

Technical Details:
-----------------
* Copies security groups membership
* Preserves all access control rules
* Clean wizard-based workflow
* No complex configuration required

Installation:
Simply install the module and access the wizard from the Users menu.
    """,
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'wizard/user_permission_copy_wizard_views.xml',
    ],
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'support': 'paulius.gaizauskas@gmail.com',
}