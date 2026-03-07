"""
Structured logging configuration for the Ethical AI Platform.

Provides:
- JSON-formatted structured logs
- Request-aware context (request_id, user_id)
- Consistent log levels and naming across all modules
- Performance timing utilities
"""

import logging
import logging.config
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Outputs each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra context fields if present
        for key in ("request_id", "user_id", "user_email", "ip_address",
                     "method", "path", "status_code", "duration_ms",
                     "action", "resource_type", "resource_id"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        # Include exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ---------------------------------------------------------------------------
# Console (human-readable) Formatter
# ---------------------------------------------------------------------------

class ConsoleFormatter(logging.Formatter):
    """Coloured, human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[35m", # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        extras = []
        for key in ("request_id", "user_id", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")
        extra_str = f" [{', '.join(extras)}]" if extras else ""
        msg = f"{color}{ts} {record.levelname:<8}{self.RESET} {record.name}: {record.getMessage()}{extra_str}"
        if record.exc_info and record.exc_info[0] is not None:
            msg += "\n" + self.formatException(record.exc_info)
        return msg


# ---------------------------------------------------------------------------
# Setup function
# ---------------------------------------------------------------------------

def setup_logging(*, json_output: bool = False, level: str = "INFO") -> None:
    """
    Configure logging for the whole application.

    Args:
        json_output: If True use JSON lines format (for production).
                     If False use coloured console format (for development).
        level: Root log level.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers (avoid duplicates on reload)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter() if json_output else ConsoleFormatter())
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpcore", "httpx",
                   "multipart", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Keep our app loggers at the requested level
    logging.getLogger("ethical_ai").setLevel(getattr(logging, level.upper(), logging.INFO))


# ---------------------------------------------------------------------------
# Helper: get a logger with the standard prefix
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``ethical_ai`` namespace."""
    return logging.getLogger(f"ethical_ai.{name}")


# ---------------------------------------------------------------------------
# Performance timer context manager
# ---------------------------------------------------------------------------

class PerfTimer:
    """Simple wall-clock timer for measuring operation duration."""

    def __init__(self, label: str = "", logger: Optional[logging.Logger] = None):
        self.label = label
        self.logger = logger
        self.start: float = 0
        self.duration_ms: float = 0

    def __enter__(self) -> "PerfTimer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.duration_ms = (time.perf_counter() - self.start) * 1000
        if self.logger:
            self.logger.info(
                "%s completed in %.1f ms",
                self.label,
                self.duration_ms,
                extra={"duration_ms": round(self.duration_ms, 1)},
            )
