import logging
import os
import re
import sys
import threading

from odoo import api, models
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)

# Set while the logger itself uses the ORM, so those calls are not logged.
_guard = threading.local()

OWN_MODELS = ("debug.logger.settings", "debug.logger.entry")
SECRET_KEY = re.compile(r"password|passwd|secret|token|api_?key", re.IGNORECASE)
MAX_VALUE_LEN = 1000
SKIP_FILES = (__file__, os.path.join("odoo", "api.py"))
SKIP_FUNCTIONS = ("__set__", "__setitem__")  # record.f = v, record["f"] = v


def _clean(value):
    """Mask secret-looking keys, keep the structure."""
    if isinstance(value, dict):
        return {
            key: "***"
            if isinstance(key, str) and SECRET_KEY.search(key)
            else _clean(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return type(value)(_clean(item) for item in value)
    return value


def _short(value):
    text = str(_clean(value))
    if len(text) > MAX_VALUE_LEN:
        return f"{text[:MAX_VALUE_LEN]}... ({len(text)} chars)"
    return text


class BaseLogger(models.AbstractModel):
    _inherit = "base"

    def _debug_log_config(self, operation):
        """Return the logger config if this call must be logged, else None."""
        if (
            self._name in OWN_MODELS
            or getattr(_guard, "active", False)
            or not self.env.registry.ready
        ):
            return None
        _guard.active = True
        try:
            config = self.env["debug.logger.settings"]._get_config()
        finally:
            _guard.active = False
        if (
            config
            and operation in config["methods"]
            and (not config["models"] or self._name in config["models"])
        ):
            return config
        return None

    def _debug_log_caller(self, operation):
        """First frame outside the ORM and the overrides of this operation."""
        frame = sys._getframe(2)
        while frame:
            code = frame.f_code
            caller = frame.f_locals.get("self")
            if not (
                code.co_filename.endswith(SKIP_FILES)
                or code.co_name in SKIP_FUNCTIONS
                or (
                    code.co_name == operation
                    and getattr(caller, "_name", None) == self._name
                )
            ):
                return f"{code.co_filename}:{frame.f_lineno} in {code.co_name}()"
            frame = frame.f_back
        return "Unknown"

    def _debug_log(self, config, operation, **kwargs):
        caller = self._debug_log_caller(operation)
        data = "".join(f"{key}: {_short(value)}\n" for key, value in kwargs.items())
        log_message = (
            f"\n{'=' * 50} DEBUG LOGGER {'=' * 50}\n"
            f"Operation: {operation.upper()}\n"
            f"Model: {self._name}\n"
            f"User: {self.env.user.name} (ID: {self.env.uid})\n"
            f"Called from: {caller}\n"
        )
        _logger.info(log_message + data + "=" * 114)
        if not config["store"]:
            return
        _guard.active = True  # storing calls the ORM too (create, cleanup unlink)
        try:
            # A failed insert must not abort the caller's transaction.
            with self.env.cr.savepoint():
                entries = self.env["debug.logger.entry"].sudo()
                entries.create(
                    {
                        "name": operation.upper(),
                        "model": self._name,
                        "data": data,
                        "caller_info": caller,
                    }
                )
                entries._cleanup(config["max_entries"])
        except Exception:
            _logger.warning("Debug logger could not store an entry", exc_info=True)
        finally:
            _guard.active = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        config = self._debug_log_config("create")
        if config:
            records._debug_log(
                config,
                "create",
                vals_list=vals_list,
                record_ids=records.ids,
                record_count=len(records),
            )
        return records

    def write(self, vals):
        config = self and self._debug_log_config("write")
        if not config:
            return super().write(vals)
        try:
            old_values = {
                record.id: {name: record[name] for name in vals if name in self._fields}
                for record in self
            }
        except (AccessError, MissingError):
            old_values = "unreadable"
        result = super().write(vals)
        self._debug_log(
            config,
            "write",
            ids=self.ids,
            vals=vals,
            old_values=old_values,
            record_count=len(self),
        )
        return result

    def unlink(self):
        config = self and self._debug_log_config("unlink")
        if not config:
            return super().unlink()
        try:
            record_data = [
                {"id": record.id, "display_name": record.display_name}
                for record in self
            ]
        except (AccessError, MissingError):
            record_data = "unreadable"
        ids = self.ids
        result = super().unlink()
        self._debug_log(
            config,
            "unlink",
            ids=ids,
            record_data=record_data,
            record_count=len(ids),
        )
        return result

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        result = super().search(domain, offset=offset, limit=limit, order=order)
        config = self._debug_log_config("search")
        if config:
            self._debug_log(
                config,
                "search",
                domain=domain,
                offset=offset,
                limit=limit,
                order=order,
                result_count=len(result),
            )
        return result

    @api.model
    def search_read(
        self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs
    ):
        result = super().search_read(
            domain=domain,
            fields=fields,
            offset=offset,
            limit=limit,
            order=order,
            **read_kwargs,
        )
        config = self._debug_log_config("search_read")
        if config:
            self._debug_log(
                config,
                "search_read",
                domain=domain,
                fields=fields,
                offset=offset,
                limit=limit,
                order=order,
                result_count=len(result),
            )
        return result
