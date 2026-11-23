## Module log_real_ip

#### 22.11.2026
#### Version 20.0.1.1.0
#### BUG FIX
- Rewritten for Odoo 20's HTTP server; the previous version changed nothing.
- Works without `X-Forwarded-Host`, and a client cannot forge the first entry.
