# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Odoo 17.0 module called "Debug Logger" that provides comprehensive database operation logging for debugging purposes. The module intercepts and logs all database operations (create, write, unlink, search, search_read) across all Odoo models.

## Architecture

### Core Components

- **BaseLogger** (`models/base_logger.py`): Abstract model that inherits from 'base' and overrides core ORM methods to add logging functionality. Uses thread-safe recursion prevention and structured logging.

- **DebugLoggerSettings** (`models/debug_log_settings.py`): Configuration model that controls logging behavior - which operations to log, which models to track, storage settings, and cleanup policies.

- **DebugLogEntry** (`models/debug_log_entry.py`): Storage model for log entries when database storage is enabled. Includes operation details, caller information, and timestamps.

### Key Design Patterns

- **Mixin Pattern**: BaseLogger inherits from 'base' to inject logging into all Odoo models
- **Recursion guard**: a `threading.local` flag is set while the logger itself uses the ORM (reading its config, storing entries), so those calls are not logged
- **Cached config**: `debug.logger.settings._get_config()` is an `ormcache`, cleared on every settings create/write/unlink; at most one configuration is active
- **Configurable Logging**: Settings model allows granular control over what gets logged
- **Caller Tracking**: walks the stack past `odoo/api.py` and the other modules' overrides of the same method to find the real caller

### Data Flow

1. Any database operation on any model triggers the overridden method in BaseLogger
2. `_debug_log_config()` checks if logging is enabled and filters based on model/operation settings; `_debug_log()` writes the log
   (keys that look like passwords/tokens are masked, long values cut at 1000 chars)
3. Structured log data is written to Odoo server logs and optionally stored in database
4. Old entries are automatically cleaned up based on max_entries setting

## Development Commands

This is an Odoo module, so standard Odoo development practices apply:

- **Install module**: Go to Apps menu in Odoo, search for "Debug Logger", and install
- **Update module**: `odoo-bin -u debug_logger -d database_name`
- **Access settings**: Debug Tools → Logger Settings (requires System Administrator access)
- **View logs**: Debug Tools → Log Entries (when storage is enabled)

## Configuration

- Default configuration is created via `data/default_config.xml`, with logging off
- Module only accessible to users in `base.group_system` (System Administrators)
- Logging can be toggled globally and per-operation type
- Model filtering available - if no models selected, all models are logged
- Storage is optional - logs always go to server logs, database storage is configurable

## Important Notes

- The module logs to standard Odoo server logs with INFO level
- Self-logging prevention: Operations on debug.logger.* models are never logged to prevent recursion
- Thread-safe implementation prevents issues in multi-threaded environments
- Includes enhanced logging with caller information and structured data formatting