# Log Real IP

Show real client IPs in werkzeug access logs when Odoo runs behind a reverse proxy.

![The same request logged without and with log_real_ip](static/description/screenshot_1.png)

## Features

- Reads `X-Forwarded-For` header (standard reverse-proxy convention)
- Falls back to `X-Real-IP` header (nginx convention)
- Activates only when `proxy_mode = True` — zero impact on direct setups
- Lightweight: a single startup patch, no database writes

## Installation

1. Copy the `log_real_ip` directory into your Odoo addons path.
2. Enable `proxy_mode = True` in `odoo.conf`.
3. Install the module from **Apps** menu.
4. Restart Odoo.

## Configuration

No configuration needed. The module reads the `proxy_mode` setting from `odoo.conf` at startup. If `proxy_mode` is `False` or unset, the patch is not applied.

## Usage

After installation and restart, werkzeug access log lines will show the originating client IP instead of the proxy's internal address:

```
127.0.0.1 - - [01/Jan/2025 12:00:00] "GET / HTTP/1.1" 200 -   # before
203.0.113.42 - - [01/Jan/2025 12:00:00] "GET / HTTP/1.1" 200 - # after
```

## Technical Details

- **Compatibility**: Odoo 17.0
- **Dependencies**: `base`
- **License**: LGPL-3
- **Approach**: Monkey-patches `werkzeug.serving.WSGIRequestHandler.address_string` at module load time
