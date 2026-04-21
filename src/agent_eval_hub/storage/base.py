"""Storage abstraction. Today backed by DuckDB; swappable to Postgres for
production deployments that outlive GitHub `actions/cache`'s 7-day eviction.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Store(ABC):
    """Minimal surface a storage backend must implement.

    Kept narrow on purpose. Anything richer (joins, window queries) happens
    inside the backend by passing raw SQL through `query_rows` — we don't
    pretend to be an ORM."""

    @abstractmethod
    def record_run(self, report, git_sha: str | None = None) -> str: ...

    @abstractmethod
    def record_divergences(self, suite: str, divergences: list[dict[str, Any]]) -> int: ...

    @abstractmethod
    def load_run_history(
        self, suite: str | None = None, provider: str | None = None
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def load_divergences(self, suite: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...

    @abstractmethod
    def find_regressions(self, suite: str, provider: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def find_token_regressions(
        self, suite: str, provider: str, min_ratio: float = 1.3
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def close(self) -> None: ...
