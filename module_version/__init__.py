from . import models
import json
from datetime import datetime


def post_init_hook(env):
    """Create initial module snapshot on first install.

    All currently installed modules are recorded as pre-existing (is_new=False)
    so they don't appear as 'Newly Added'. Only modules installed after this
    point will show the NEW badge.
    """
    modules = env['ir.module.module'].search([('state', '=', 'installed')])
    now = datetime.utcnow().isoformat()
    snapshot = {
        m.name: {'version': m.latest_version or '', 'since': now, 'is_new': False}
        for m in modules
    }
    env['ir.config_parameter'].sudo().set_param(
        'module_version.installed_snapshot', json.dumps(snapshot)
    )
