"""
Per-leg best-ask momentum vs a rolling window minimum, for staggered two-leg BUY playbooks.

UP ask rising strongly → buy UP first, then the other leg after a delay.
DOWN ask rising strongly → buy DOWN first, then UP after a delay.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from polymarket_analyzer.trading.arbitrage import quantize_arb_price


def rise_bps_vs_window_min(
    samples: Sequence[tuple[int, float]],
    *,
    now_ms: int,
    window_ms: int,
) -> Optional[float]:
    """
    Compare the latest ask in ``window_ms`` to the **minimum** ask in that window.
    Return rise in basis points: ``(last / min - 1) * 10_000``, or None if not enough data.
    """
    lo_t = int(now_ms) - int(window_ms)
    pts: list[tuple[int, float]] = []
    for t, a in samples:
        if int(t) < lo_t or not (a > 0.0) or a != a:
            continue
        qa = quantize_arb_price(float(a))
        if qa is not None:
            pts.append((int(t), qa))
    if len(pts) < 2:
        return None
    pts.sort(key=lambda x: x[0])
    asks = [p[1] for p in pts]
    mn = min(asks)
    last = pts[-1][1]
    if mn <= 0.0:
        return None
    return (last / mn - 1.0) * 10_000.0


def staggered_hedge_order(
    up_rise_bps: Optional[float],
    dn_rise_bps: Optional[float],
    *,
    min_rise_bps: float,
) -> Optional[Tuple[str, str]]:
    """
    (first_leg, second_leg) each ``\"UP\"`` or ``\"DOWN\"`` for BUY order.

    If both legs meet ``min_rise_bps``, the **stronger** rise leads (tie → UP leads).
    If only one qualifies, that leg leads.
    """
    u = float(up_rise_bps) if up_rise_bps is not None else -1.0
    d = float(dn_rise_bps) if dn_rise_bps is not None else -1.0
    u_ok = u >= float(min_rise_bps)
    d_ok = d >= float(min_rise_bps)
    if u_ok and d_ok:
        if u >= d:
            return ("UP", "DOWN")
        return ("DOWN", "UP")
    if u_ok:
        return ("UP", "DOWN")
    if d_ok:
        return ("DOWN", "UP")
    return None
