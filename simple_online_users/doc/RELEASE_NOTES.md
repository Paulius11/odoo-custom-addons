## Module simple_online_users

#### 22.11.2026
#### Version 19.0.1.0.2
#### BUG FIX
- Security: portal users could read the names and logins of online staff; the server now checks the setting.
- Removed the "Portal Users" choice; databases that used it are set back to System Administrators.
- The widget no longer turns Away users Online.
- The status is the one Discuss shows: connected users no longer drop out after 5 minutes.
- The count always matches the list.
- Upgrading the module no longer resets the visibility setting.
- Users who set themselves Offline are not listed.
- Routes use `jsonrpc` (the `json` type is deprecated).

#### 28.10.2026
#### Version 19.0.1.0.1
#### BUG FIX
- Fixed the web client failing to load after install: Odoo 18 removed the `rpc` and `user` services.
- Fixed the count always showing 0: Odoo 19 moved presence to `mail.presence` (now depends on Discuss/`mail`).
#### UPDATE
- New Apps Store page and screenshot.
