## Module module_version

#### 22.11.2026
#### Version 18.0.4.2.3
#### BUG FIX
- History records the old and the new version; upgrades were logged as new to new. Older entries are unchanged.
- Failed installs, upgrades and uninstalls are recorded in the history.

#### 28.10.2026
#### Version 18.0.4.2.1
#### BUG FIX
- Fixed install failing on Odoo 18: `<tree>` views, Apps kanban hooks written for the 17.0 card, and the removed cron field `numbercall`.
