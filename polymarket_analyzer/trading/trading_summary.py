"""
Helpers to summarize bundle BUY attempts (sim + real) for UI: cost / fee / PnL vs $1 resolution.

PnL is **estimated** from the limit prices and GUI fee assumption (same fee model as ``arbitrage``).
Real fills may differ; API bodies are shown truncated in the log.
"""

from __future__ import annotations

import json
from typing import Any, Mapping


def single_leg_buy_cost(*, shares: float, price: float, fee_bps_each_leg: float) -> dict[str, float]:
    """Notional on one leg: gross = price * shares, fee = (bps/1e4) * gross, cost = gross + fee."""
    fee_rate = float(fee_bps_each_leg) / 10000.0
    sh = float(shares)
    px = float(price)
    gross = px * sh
    fee = fee_rate * gross
    cost = gross + fee
    return {"gross_leg": gross, "fee_leg": fee, "total_cost": cost}


def bundle_buy_cost_and_pnl(
    *,
    shares: float,
    up_price: float,
    down_price: float,
    fee_bps_each_leg: float,
) -> dict[str, float]:
    """
    Per pair: gross = up + down, fee = (bps/1e4) * gross, cost = gross + fee.
    PnL if one matched pair pays $1 USDC at resolution: ``shares * (1 - cost_per_pair)``.
    """
    fee_rate = float(fee_bps_each_leg) / 10000.0
    gross = float(up_price) + float(down_price)
    fee = fee_rate * gross
    cost_per = gross + fee
    edge_per = 1.0 - cost_per
    sh = float(shares)
    return {
        "gross_per_pair": gross,
        "fee_per_pair": fee,
        "cost_per_pair": cost_per,
        "edge_per_pair": edge_per,
        "total_cost": sh * cost_per,
        "pnl_at_resolution": sh * edge_per,
    }


def format_clob_response_cell(resp: Any, *, max_len: int = 72) -> str:
    """One-line summary for a table cell."""
    if resp is None:
        return "—"
    if isinstance(resp, dict):
        if resp.get("simulated"):
            oid = resp.get("order_id") or resp.get("orderID")
            if oid:
                return f"sim ok id={oid}"[:max_len]
            return "sim (no post)"[:max_len]
        for key in ("orderID", "order_id", "id", "errorMsg", "error", "message", "status", "success"):
            if key in resp and resp[key] is not None and resp[key] != "":
                v = resp[key]
                s = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                return f"{key}={s}"[:max_len]
        try:
            return json.dumps(resp, separators=(",", ":"))[:max_len]
        except (TypeError, ValueError):
            return str(resp)[:max_len]
    s = str(resp).replace("\n", " ")
    return s[:max_len] + ("…" if len(s) > max_len else "")


def cumulative_pnl_by_mode(rows: list[Mapping[str, Any]]) -> tuple[float, float]:
    sim = 0.0
    real = 0.0
    for r in rows:
        m = str(r.get("mode", "")).upper()
        p = float(r.get("pnl_est", 0.0) or 0.0)
        if m == "SIM":
            sim += p
        elif m == "REAL":
            real += p
    return sim, real


def session_leg_shares_for_slug(rows: list[Mapping[str, Any]], *, slug: str) -> tuple[float, float]:
    """
    Sum single-leg BUY shares from the session log for an exact ``slug`` match.
    Rows should include ``leg`` (``\"UP\"`` / ``\"DOWN\"``); older rows without ``leg`` are ignored.
    Returns ``(up_shares, down_shares)``.
    """
    slug_n = (slug or "").strip()
    up_total = 0.0
    dn_total = 0.0
    for r in rows:
        if str(r.get("slug", "")).strip() != slug_n:
            continue
        leg = str(r.get("leg", "")).strip().upper()
        sh = float(r.get("shares", 0.0) or 0.0)
        if sh <= 0.0 or sh != sh:
            continue
        if leg == "UP":
            up_total += sh
        elif leg == "DOWN":
            dn_total += sh
    return up_total, dn_total
