"""
Load `.env` and read Polymarket / CLOB-related variables.

Expected variables (all optional; SQLite can still supply secrets):

- ``PM_PRIVATE_KEY`` — EOA private key (hex, with or without ``0x``).  
  Aliases: ``POLYMARKET_PRIVATE_KEY``, ``PRIVATE_KEY``.
- ``PM_SIG_TYPE`` — signature type (``0`` = EOA, ``1`` = POLY_PROXY, ``2`` = Gnosis Safe). Alias: ``POLYMARKET_SIG_TYPE``.
  The CLOB vault address is derived from the key and this type unless you override (see ``funder_resolve_for_clob``).
- ``PM_RPC_URL`` — Polygon JSON-RPC for allowance / approval checks. Alias: ``POLYGON_RPC_URL``.
- ``PM_BUILDER_KEY`` / ``PM_BUILDER_SECRET`` / ``PM_BUILDER_PASSPHRASE`` — Polymarket **builder** API
  credentials (required for relayer approvals with ``PM_SIG_TYPE`` 1 or 2).
  Aliases: ``PM_BUILDER_API_KEY`` for the key only.
- ``PM_SIMULATE`` — if truthy (``1``, ``true``, ``yes``, ``on``), CLOB bundle execution does not call
  ``post_order`` (live book data only). Alias: ``POLYMARKET_SIMULATE``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def load_app_env(*, override: bool = False) -> bool:
    """
    Load ``.env`` from the current working directory, then parent, then default lookup.
    Returns True if a ``.env`` file was found and loaded.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    for base in (Path.cwd(), Path.cwd().parent):
        env_path = base / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=override)
            return True
    load_dotenv(override=override)
    return False


def _strip_quotes(v: str) -> str:
    s = v.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1].strip()
    return s


def private_key_from_env() -> Optional[str]:
    for key in ("PM_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY", "PRIVATE_KEY"):
        raw = os.environ.get(key)
        if raw and str(raw).strip():
            s = _strip_quotes(str(raw))
            if s.startswith("0x"):
                return s
            return s if s else None
    return None


def funder_from_env() -> Optional[str]:
    for key in ("PM_FUNDER", "POLYMARKET_FUNDER"):
        raw = os.environ.get(key)
        if raw and str(raw).strip():
            return _strip_quotes(str(raw))
    return None


def _truthy_env_flag(raw: Optional[str]) -> bool:
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def simulate_clob_orders_from_env() -> bool:
    """True when ``PM_SIMULATE`` / ``POLYMARKET_SIMULATE`` requests simulated CLOB posts (no real orders)."""
    return _truthy_env_flag(os.environ.get("PM_SIMULATE") or os.environ.get("POLYMARKET_SIMULATE"))


def simulate_clob_orders_forced_by_env() -> bool:
    """When True, simulation cannot be turned off from the GUI (environment overrides)."""
    return simulate_clob_orders_from_env()


def simulate_clob_orders_resolve(sqlite_fallback: Optional[str] = None) -> bool:
    if simulate_clob_orders_from_env():
        return True
    return _truthy_env_flag(sqlite_fallback)


def funder_resolve_for_clob(
    private_key: str,
    signature_type: int,
    explicit_funder: Optional[str],
) -> str:
    """
    Resolve the CLOB ``funder`` (trading vault) address.

    If ``explicit_funder`` is set (e.g. env ``PM_FUNDER`` / SQLite ``pm_funder``), returns that address checksummed.
    Otherwise: signature type ``0`` → signer EOA; types ``1`` or ``2`` → Polymarket CREATE2 Safe
    for this private key (same derivation as the relayer).
    """
    ex = (explicit_funder or "").strip()
    if ex:
        from web3 import Web3

        return Web3.to_checksum_address(ex)
    st = int(signature_type)
    if st == 0:
        from polymarket_analyzer.chain.approvals import eoa_checksum_address

        return eoa_checksum_address(private_key)
    from polymarket_analyzer.chain.approvals import derived_safe_funder_address

    return derived_safe_funder_address(private_key)


def sig_type_from_env() -> Optional[int]:
    raw = os.environ.get("PM_SIG_TYPE") or os.environ.get("POLYMARKET_SIG_TYPE")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def rpc_url_from_env() -> Optional[str]:
    for key in ("PM_RPC_URL", "POLYGON_RPC_URL"):
        raw = os.environ.get(key)
        if raw and str(raw).strip():
            return _strip_quotes(str(raw))
    return None


def builder_key_from_env() -> Optional[str]:
    for key in ("PM_BUILDER_KEY", "PM_BUILDER_API_KEY"):
        raw = os.environ.get(key)
        if raw and str(raw).strip():
            return _strip_quotes(str(raw))
    return None


def builder_secret_from_env() -> Optional[str]:
    raw = os.environ.get("PM_BUILDER_SECRET")
    if raw and str(raw).strip():
        return _strip_quotes(str(raw))
    return None


def builder_passphrase_from_env() -> Optional[str]:
    raw = os.environ.get("PM_BUILDER_PASSPHRASE")
    if raw and str(raw).strip():
        return _strip_quotes(str(raw))
    return None


def sig_type_resolve(sqlite_fallback: Optional[str] = None) -> int:
    st = sig_type_from_env()
    if st is not None:
        return st
    if sqlite_fallback is not None and str(sqlite_fallback).strip() != "":
        try:
            return int(str(sqlite_fallback).strip())
        except ValueError:
            pass
    return 0
