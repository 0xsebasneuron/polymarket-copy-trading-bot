"""Read Polygon native (POL) balance on the signer EOA and pUSD collateral on the CLOB trading vault."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from polymarket_analyzer.chain.approvals import (
    _clob_polygon_configs,
    make_web3,
    resolve_trading_context,
)


_ERC20_BAL_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


@dataclass
class WalletSnapshot:
    eoa: str
    trading_address: str
    rpc_url: str
    eoa_pol: Optional[float]
    trading_usdc: Optional[float]
    error: Optional[str] = None


def fetch_wallet_snapshot(
    *,
    private_key: Optional[str],
    rpc_url: Optional[str],
    signature_type: int,
    funder_explicit: Optional[str],
) -> WalletSnapshot:
    """
    ``private_key`` hex (with or without 0x). If missing or invalid, returns ``error`` set.
    """
    pk = (private_key or "").strip()
    if not pk:
        return WalletSnapshot(
            eoa="—",
            trading_address="—",
            rpc_url=(rpc_url or "").strip() or "(default RPC)",
            eoa_pol=None,
            trading_usdc=None,
            error="No PM_PRIVATE_KEY (or SQLite pm_private_key).",
        )
    url_used = (rpc_url or "").strip() or "https://polygon-bor-rpc.publicnode.com"
    try:
        w3 = make_web3(rpc_url)
        ctx = resolve_trading_context(
            private_key=pk,
            funder=(funder_explicit or "").strip() or None,
            signature_type=int(signature_type),
            w3=w3,
        )
        std, _ = _clob_polygon_configs()
        collateral = Web3.to_checksum_address(std.collateral)
        c = w3.eth.contract(address=collateral, abi=_ERC20_BAL_ABI)
        raw_usdc = int(c.functions.balanceOf(ctx.trading_address).call())
        try:
            dec = int(c.functions.decimals().call())
        except Exception:
            dec = 6
        usdc = raw_usdc / float(10**dec)
        pol_wei = int(w3.eth.get_balance(ctx.eoa))
        pol = float(w3.from_wei(pol_wei, "ether"))
        return WalletSnapshot(
            eoa=ctx.eoa,
            trading_address=ctx.trading_address,
            rpc_url=url_used,
            eoa_pol=pol,
            trading_usdc=usdc,
            error=None,
        )
    except Exception as e:
        return WalletSnapshot(
            eoa="—",
            trading_address="—",
            rpc_url=url_used,
            eoa_pol=None,
            trading_usdc=None,
            error=str(e),
        )


def format_wallet_snapshot_line(s: WalletSnapshot, *, max_addr: int = 10) -> str:
    if s.error:
        return f"Wallet: {s.error} (RPC: {s.rpc_url})"

    def short(a: str) -> str:
        a = a.strip()
        if len(a) <= 2 + max_addr * 2:
            return a
        return f"{a[:6]}…{a[-4:]}"

    pol_s = f"{s.eoa_pol:.4f} POL" if s.eoa_pol is not None else "— POL"
    usdc_s = f"{s.trading_usdc:,.2f} pUSD" if s.trading_usdc is not None else "— pUSD"
    return (
        f"EOA {short(s.eoa)}: {pol_s}  |  Vault {short(s.trading_address)}: {usdc_s}  |  RPC {s.rpc_url}"
    )
