"""Polymarket Analyzer — live UP/DOWN books, paired cost vs $1 par, optional single-leg CLOB execution (PyQt + CLI)."""

from __future__ import annotations

from typing import Any

from polymarket_analyzer.infra.sqlite_store import (
    sqlite_delete_secret,
    sqlite_get_path_str,
    sqlite_load_secret,
    sqlite_save_secret,
)
from polymarket_analyzer.core.supervisor import MarketSupervisor, SupervisorCallbacks

__all__ = [
    "MarketSupervisor",
    "SupervisorCallbacks",
    "sqlite_delete_secret",
    "sqlite_get_path_str",
    "sqlite_load_secret",
    "sqlite_save_secret",
    "run_gui",
]


def __getattr__(name: str) -> Any:
    if name == "run_gui":
        from polymarket_analyzer.ui.run import run_gui as rg

        globals()["run_gui"] = rg
        return rg
    raise AttributeError(f"{__name__!r} has no attribute {name!r}")
