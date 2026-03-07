{
    'name': 'Log Real IP',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Show real client IP in werkzeug logs when behind a reverse proxy',
    'description': """
Log Real IP
===========
When Odoo runs behind a reverse proxy (nginx, Caddy, Apache), werkzeug logs
the proxy's internal IP instead of the actual client IP. This module patches
werkzeug's address_string to read the X-Forwarded-For or X-Real-IP header,
so the real client IP appears in access logs.

Activation:
-----------
The patch applies automatically when Odoo is started with proxy_mode = True
in odoo.conf. No additional configuration is required.

Key Features:
-------------
* Reads X-Forwarded-For header (standard proxy header)
* Falls back to X-Real-IP header (nginx convention)
* Only activates when proxy_mode is enabled — zero impact otherwise
* Lightweight: a single monkey-patch at startup, no database writes

Perfect For:
------------
* Odoo deployments behind nginx, Caddy, or Apache
* Auditing real client IPs in werkzeug access logs
* Debugging geo-restricted or IP-based access policies
    """,
    'author': 'Paulius Gaizauskas',
    'maintainer': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'email': 'paulius.gaizauskas@gmail.com',
    'support': 'paulius.gaizauskas@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base'],
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
