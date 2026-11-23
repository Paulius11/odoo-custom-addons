## Module simple_online_users

#### 22.11.2026
#### Version 17.0.1.0.2
#### BUG FIX
- Security: portal users could read the names and logins of online staff; the server now checks the setting.
- Removed the "Portal Users" choice; databases that used it are set back to System Administrators.
- The widget no longer turns Away users Online.
- The status is the one Discuss shows: connected users no longer drop out after 5 minutes.
- The count always matches the list.
- Upgrading the module no longer resets the visibility setting.
