## Module debug_logger

#### 17.11.2026
#### Version 17.0.1.2.0
#### BUG FIX
- `search_read(..., load=False)` no longer fails with `TypeError` (seen in MRP, Repair and PoS online payment).
- Logging is off after install; the module's own install no longer floods the server log.
- Each ORM call no longer runs extra searches for the settings; the configuration is cached.
- Passwords, tokens and API keys are masked; long values are cut at 1000 characters.
- A write or delete no longer fails when the old values cannot be read.
- "Called From" shows the code that made the call, not another module's override or `record.field = value`.
- A failed entry insert no longer aborts the caller's transaction; storing entries can no longer loop.
- Only one configuration is active: the last one created or activated.
- Empty writes and deletes are not logged.
#### UPDATE
- Stored operation data is one line per key; Log Entries can search inside it.
- Removed the `track_method` decorator: it never logged anything.
- New Apps Store page, README, banner, icon and screenshots; tests added.
