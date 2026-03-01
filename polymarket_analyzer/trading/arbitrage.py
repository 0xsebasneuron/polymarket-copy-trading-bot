"""
UP / DOWN paired CLOB math vs $1 resolution.

All **price** quantities used here are quantized to ``ARB_PRICE_TICK`` (0.01) so diagnostics and
thresholds align with a 1¢ CLOB-style step.

``cross_time_min_ask_sum_vs_par`` tracks the **minimum** UP ask and **minimum** DOWN ask over a
rolling window (possibly at different timestamps ``t1``, ``t2``), which can sum below $1 even when
every **single** snapshot shows an over-par pair.

``buy_bundle_opportunity_at_asks`` builds a **current-touch** two-leg BUY quote (sizes + prices)
for execution / paper PnL — not a same-timestamp “arb detector”.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

ARB_PRICE_TICK = 0.01


def quantize_arb_price(x: Optional[float]) -> Optional[float]:
    """Round a positive finite price to ``ARB_PRICE_TICK`` (half-up); else return ``None``."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not (v > 0.0) or v != v:
        return None
    return round(v / ARB_PRICE_TICK) * ARB_PRICE_TICK


class ArbKind(str, Enum):
    BUY_BUNDLE = "buy_bundle"  # buy UP @ ask + buy DOWN @ ask


@dataclass(frozen=True)
class BundleArbOpportunity:
    kind: ArbKind
    """At these asks: ``1 - net_cost`` per pair (often ≤ 0 when the touch is over par)."""
    edge_per_unit: float
    """Shares executable on both legs at displayed top of book."""
    max_size: float
    up_price: float
    down_price: float
    bundle_cost_or_proceeds: float


def prune_ask_samples_by_age(
    samples: Sequence[tuple[int, float]],
    *,
    now_ms: int,
    window_ms: int,
) -> list[tuple[int, float]]:
    """Keep (timestamp_ms, best_ask) within ``(now_ms - window_ms, now_ms]`` with positive finite asks."""
    lo = int(now_ms) - int(window_ms)
    out: list[tuple[int, float]] = []
    for t, a in samples:
        if t < lo:
            continue
        if a is None or not (a > 0) or a != a:  # NaN
            continue
        qa = quantize_arb_price(float(a))
        if qa is None:
            continue
        out.append((int(t), qa))
    return out


def cross_time_min_ask_sum_vs_par(
    *,
    up_samples: Sequence[tuple[int, float]],
    down_samples: Sequence[tuple[int, float]],
    now_ms: int,
    window_ms: int,
    fee_rate_each_leg: float = 0.0,
) -> Optional[tuple[float, int, float, int, float, float, float]]:
    """
    Cheapest UP ask and cheapest DOWN ask **within the same rolling window**, possibly at **different
    timestamps** ``t1`` and ``t2``. Return tuple
    ``(up_ask, t_up_ms, down_ask, t_dn_ms, gross_sum, net_after_fees, net_minus_par)``.

    This answers whether there existed quotes such that ``ask_up(t1) + ask_down(t2)`` (plus the
    simple per-leg fee model on the sum) could fall below $1 par, even when at every **single**
    snapshot the paired asks stayed over par.

    Fills in reality still require posting at **current** prices — this is a **diagnostic** floor.
    """
    up = prune_ask_samples_by_age(up_samples, now_ms=now_ms, window_ms=window_ms)
    dn = prune_ask_samples_by_age(down_samples, now_ms=now_ms, window_ms=window_ms)
    if not up or not dn:
        return None
    t_u, a_u = min(up, key=lambda x: x[1])
    t_d, a_d = min(dn, key=lambda x: x[1])
    gross = a_u + a_d
    fees = fee_rate_each_leg * gross
    net = gross + fees
    return a_u, t_u, a_d, t_d, gross, net, net - 1.0


def buy_bundle_opportunity_at_asks(
    *,
    up_best_ask: Optional[float],
    down_best_ask: Optional[float],
    up_ask_size: Optional[float],
    down_ask_size: Optional[float],
    fee_rate_each_leg: float = 0.0,
) -> Optional[BundleArbOpportunity]:
    """
    BUY both legs at current best asks with top-of-book size cap — even when ``1 - net_cost`` ≤ 0.

    Asks are quantized to ``ARB_PRICE_TICK`` before gross / edge math.
    Up/Down books are usually **over par**, so this path is for workflow / PnL-at-resolution estimates.
    """
    up_p = quantize_arb_price(up_best_ask)
    dn_p = quantize_arb_price(down_best_ask)
    if (
        up_p is not None
        and dn_p is not None
        and up_ask_size is not None
        and down_ask_size is not None
        and up_ask_size > 0
        and down_ask_size > 0
    ):
        gross = up_p + dn_p
        fees = fee_rate_each_leg * gross
        net_cost = gross + fees
        edge = 1.0 - net_cost
        return BundleArbOpportunity(
            kind=ArbKind.BUY_BUNDLE,
            edge_per_unit=float(edge),
            max_size=float(min(up_ask_size, down_ask_size)),
            up_price=float(up_p),
            down_price=float(dn_p),
            bundle_cost_or_proceeds=float(net_cost),
        )
    return None
