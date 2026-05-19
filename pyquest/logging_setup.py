"""Local rotating log file at userdata/logs/pyquest.log.

No telemetry, no network. The file is a help when users file a GitHub issue
so they can attach it. Rotated so it never gets huge.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys

from pyquest.config import USERDATA_DIR

LOG_DIR = USERDATA_DIR / "logs"
LOG_FILE = LOG_DIR / "pyquest.log"


def setup_logging(level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if getattr(root, "_pyquest_configured", False):
        return  # idempotent, safe to call twice
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    # Also stream to console so terminal users still see warnings.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    stderr_handler.setLevel(logging.WARNING)
    root.addHandler(stderr_handler)

    # Hook unhandled exceptions through logging so the crash makes it into the file.
    def _excepthook(exc_type, exc_value, tb):
        logging.getLogger("pyquest.crash").critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, tb)
        )
        sys.__excepthook__(exc_type, exc_value, tb)

    sys.excepthook = _excepthook
    root._pyquest_configured = True  # type: ignore[attr-defined]


def tail_log(lines: int = 80) -> str:
    if not LOG_FILE.exists():
        return "(no log entries yet)"
    try:
        with LOG_FILE.open("r", encoding="utf-8", errors="replace") as fh:
            data = fh.readlines()
        return "".join(data[-lines:])
    except OSError as exc:
        return f"(could not read log: {exc})"
