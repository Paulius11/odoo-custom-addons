## Module mail_lost

#### 22.11.2026
#### Version 20.0.1.1.1
#### BUG FIX
- Create a record no longer offers User, which always failed for lack of a login.

#### 18.11.2026
#### Version 19.0.1.1.0
#### UPDATE
- Emails written straight to the catchall address are kept as lost emails instead of bounced.
- The Route dialog hides technical models (`ir.*`, `iap.*`, `base.*`, `bus.*`, `*.blacklist`).

#### 18.11.2026
#### Version 19.0.1.0.0
#### NEW
- Keep incoming emails Odoo cannot route; route them to a record or create one from them.
