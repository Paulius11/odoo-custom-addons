## Module module_version

#### 22.11.2026
#### Version 20.0.4.2.3
#### BUG FIX
- History records the old and the new version; upgrades were logged as new to new. Older entries are unchanged.
- Failed installs, upgrades and uninstalls are recorded in the history.
- Fixed the Updates Available (always empty), Newly Added and Recently Upgraded (inverted) filters.
- The update list shows the module name instead of the technical name.

#### 28.10.2026
#### Version 19.0.4.2.1
#### BUG FIX
- Fixed install failing on Odoo 19: `<tree>` views, Apps kanban hooks written for the 17.0 card, the removed cron field `numbercall`, and search groups using the removed `expand` attribute.
