# -*- coding: utf-8 -*-
import re
import hashlib
import logging

_logger = logging.getLogger(__name__)

LOG_REGEX = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+(\d+)\s+'
    r'(ERROR|CRITICAL|WARNING)\s+(\S+)\s+(\S+):\s+(.+)$'
)


class LogFileParser:

    @staticmethod
    def read_new_lines(log_path, last_offset):
        """Read bytes from last_offset to EOF. Resets offset on log rotation."""
        try:
            with open(log_path, 'rb') as f:
                f.seek(0, 2)
                size = f.tell()
                if size < last_offset:
                    last_offset = 0  # rotation detected
                f.seek(last_offset)
                data = f.read()
                new_offset = f.tell()
            lines = data.decode('utf-8', errors='replace').splitlines()
            return lines, new_offset
        except (OSError, IOError) as e:
            _logger.warning('log_monitor: cannot read %s: %s', log_path, e)
            return [], last_offset

    @staticmethod
    def parse_events(lines, level_filter=('ERROR', 'CRITICAL', 'WARNING')):
        """Return list of event dicts for lines matching the Odoo log regex.

        Traceback lines and other non-matching lines are silently skipped.
        """
        events = []
        for line in lines:
            m = LOG_REGEX.match(line)
            if not m:
                continue
            ts, pid, level, db, module, message = m.groups()
            if level not in level_filter:
                continue
            dedup_key = hashlib.md5(
                f'{level}|{module}|{message[:120]}'.encode()
            ).hexdigest()
            events.append({
                'timestamp_str': ts,
                'level': level,
                'db_name': db,
                'module': module,
                'message': message.strip(),
                'dedup_key': dedup_key,
            })
        return events
