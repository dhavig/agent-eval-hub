"""Storage factory. Pick a backend by URL scheme:
    <path>.duckdb       -> DuckDBStore
    postgres://...      -> PostgresStore
"""
from __future__ import annotations

from pathlib import Path

from agent_eval_hub.storage.base import Store


def get_store(target: str | Path) -> Store:
    s = str(target)
    if s.startswith(("postgres://", "postgresql://")):
        from agent_eval_hub.storage.postgres import PostgresStore
        return PostgresStore(s)
    from agent_eval_hub.storage.duckdb import DuckDBStore
    return DuckDBStore(s)


__all__ = ["Store", "get_store"]
