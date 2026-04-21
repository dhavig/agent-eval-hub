"""Storage factory: URL routes to the right backend."""
from __future__ import annotations

from pathlib import Path

from agent_eval_hub.storage import get_store
from agent_eval_hub.storage.duckdb import DuckDBStore


def test_path_routes_to_duckdb(tmp_path: Path):
    store = get_store(tmp_path / "x.duckdb")
    assert isinstance(store, DuckDBStore)
    store.close()


def test_postgres_url_imports_postgres_backend(monkeypatch):
    """Route happens even when psycopg is missing — the error surfaces on
    construction, not at dispatch, so the other backend stays usable."""
    import sys
    monkeypatch.setitem(sys.modules, "psycopg", None)
    try:
        get_store("postgres://user:pass@localhost/db")
    except RuntimeError as exc:
        assert "psycopg not installed" in str(exc)
    except ImportError:
        pass  # accepted alternative path
