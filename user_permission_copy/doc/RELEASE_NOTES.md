## Module user_permission_copy

#### 22.11.2026
#### Version 20.0.1.0.3
#### BUG FIX
- An administrator can no longer copy onto themselves and lose admin rights.
- Copying no longer replaces the target contact's tags, which are not permissions.
- Cancel works on an empty form.
- The dialog closes after a successful copy.

#### 28.10.2026
#### Version 19.0.1.0.1
#### BUG FIX
- Fixed install failing on Odoo 19 and security groups not being copied: Odoo 19 renamed `groups_id` to `group_ids`.
