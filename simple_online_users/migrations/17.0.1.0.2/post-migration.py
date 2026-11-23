def migrate(cr, version):
    # "Portal Users" is no longer a choice: it exposed staff names and logins
    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = 'base.group_system'
         WHERE key = 'online_users.visibility_group'
           AND value = 'base.group_portal'
        """
    )
