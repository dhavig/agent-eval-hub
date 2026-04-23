"""Structured logging: JSON format when stdout isn't a TTY."""
from __future__ import annotations

import json
import logging

from agent_eval_hub.logging import _CompactFormatter


def test_formatter_emits_json_when_not_tty(monkeypatch):
    """Directly test the formatter — avoids the fact that our module installs
    a handler bound to sys.stdout *at import time*, which pytest's capture
    fixtures can't retroactively redirect."""
    import sys
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    fmt = _CompactFormatter()
    record = logging.LogRecord(
        name="agent_eval_hub.test", level=logging.INFO, pathname="", lineno=0,
        msg="hello world", args=(), exc_info=None,
    )
    out = fmt.format(record)
    parsed = json.loads(out)
    assert parsed["msg"] == "hello world"
    assert parsed["level"] == "INFO"


def test_formatter_emits_plain_when_tty(monkeypatch):
    import sys
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    fmt = _CompactFormatter()
    record = logging.LogRecord(
        name="agent_eval_hub.test", level=logging.WARNING, pathname="", lineno=0,
        msg="uh oh", args=(), exc_info=None,
    )
    out = fmt.format(record)
    assert "uh oh" in out
    assert "WARNING" in out
    # Not JSON.
    assert not out.startswith("{")


def test_logger_namespace_rooted():
    from agent_eval_hub.logging import get_logger
    log = get_logger("foo.bar")
    assert log.name.startswith("agent_eval_hub.")
