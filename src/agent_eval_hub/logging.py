"""Structured logging for the harness.

Why a custom wrapper, not stdlib directly: we want consistent formatting across
CLI runs + CI logs (plain text on TTY, JSON-ish when piped), a single knob to
dial verbosity via `AGENT_EVAL_LOG`, and no third-party dependency.

Callers: `log = get_logger(__name__)`, then `log.info(...)` as normal. Previous
`print()` statements in the runners now use this.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


class _CompactFormatter(logging.Formatter):
    """Plain text on TTY; single-line JSON when stdout is redirected (CI logs)."""

    def format(self, record: logging.LogRecord) -> str:
        if sys.stdout.isatty():
            return f"{record.levelname:<5} {record.name}: {record.getMessage()}"
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_CONFIGURED = False


def _configure_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.environ.get("AGENT_EVAL_LOG", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_CompactFormatter())
    root = logging.getLogger("agent_eval_hub")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger. Name is typically `__name__`."""
    _configure_once()
    # Normalize names outside the package so they still nest under our root.
    if not name.startswith("agent_eval_hub"):
        name = f"agent_eval_hub.{name}"
    return logging.getLogger(name)
