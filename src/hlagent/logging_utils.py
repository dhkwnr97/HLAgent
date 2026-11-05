"""Structured logging with secret redaction.

Every handler created here masks API-key-like tokens and any secret registered with
`register_secret`, so keys typed in the GUI cannot leak into logs or run directories.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

_KEY_PATTERNS = [
    re.compile(r"sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"tvly-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|authorization|x-goog-api-key)(\s*[:=]\s*)(\S+)"),
]

_secrets: set[str] = set()
_lock = threading.Lock()


def register_secret(value: str | None) -> None:
    if value and len(value) >= 8:
        with _lock:
            _secrets.add(value)


def redact(text: str) -> str:
    with _lock:
        secrets = sorted(_secrets, key=len, reverse=True)
    for s in secrets:
        text = text.replace(s, "***REDACTED***")
    for pat in _KEY_PATTERNS[:3]:
        text = pat.sub("***REDACTED***", text)
    text = _KEY_PATTERNS[3].sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(f, RedactingFilter) for f in logger.filters):
        logger.addFilter(RedactingFilter())
    return logger


def add_jsonl_handler(logger: logging.Logger, path: Path) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    logger.addHandler(handler)
    return handler
