## Module log_real_ip

#### 22.11.2026
#### Version 18.0.1.0.2
#### BUG FIX
- Security: a client could forge the logged IP; the entry added by the proxy is logged now.
- A value that is not an IP address is never written to the log.
