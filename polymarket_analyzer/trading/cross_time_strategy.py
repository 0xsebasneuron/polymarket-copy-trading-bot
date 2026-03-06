"""
Cross-time patterns on **pair gross** ``g(t) = best_ask_up(t) + best_ask_down(t)`` (same clock, two legs).

These are **diagnostic / playbook** hints, not guaranteed fills:

- **Rise then cheap**: gross rose from the start of the window to a peak, then the *current* gross
  sits at least ``pullback_bps`` below that peak — playbook: consider buying **the same share
  count** on UP and DOWN at the **current** touch (possibly with a delay between posts).
- **Sell after rising again**: after a post-peak trough, current gross has recovered by
  ``recovery_bps`` from that trough — playbook: consider selling both at **bids** (needs
  inventory). Execution of sells is separate from the BUY bundle button.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from polymarket_analyzer.trading.arbitrage import quantize_arb_price


def pair_swing_summary(
    series: Sequence[tuple[int, float]],
    *,
    now_ms: int,
    window_ms: int,
    rise_min_bps: float,
    pullback_bps: float,
    recovery_bps: float,
) -> str:
    """
    ``series`` entries are ``(timestamp_ms, gross_pair_ask)`` sorted or unsorted.

    Returns a short multi-line human summary, or empty string if not enough data.
    """
    lo = int(now_ms) - int(window_ms)
    pts: list[tuple[int, float]] = []
    for t, g in series:
        if int(t) < lo or not (g > 0.0) or g != g:
            continue
        qg = quantize_arb_price(float(g))
        if qg is not None:
            pts.append((int(t), qg))
    if len(pts) < 4:
        return ""

    pts.sort(key=lambda x: x[0])
    g_first = pts[0][1]
    g_last = pts[-1][1]
    t_last = pts[-1][0]
    g_hi, t_hi = max(pts, key=lambda x: x[1])

    rise_frac = (g_hi / max(g_first, 1e-12)) - 1.0
    rise_ok = rise_frac * 10_000.0 >= float(rise_min_bps)

    pull = float(pullback_bps) / 10_000.0
    cheap_vs_peak = rise_ok and g_last <= g_hi * (1.0 - pull)

    lines: list[str] = []
    if cheap_vs_peak:
        lines.append(
            f"Swing (pair gross): rose from {g_first:.4f} to peak {g_hi:.4f}, now {g_last:.4f} "
            f"(>={pullback_bps:.0f} bps under peak) — playbook: **same-size BUY** UP then DOWN at "
            f"**current** asks (optional leg delay); not the old t1/t2 floor."
        )

    post_peak = [p for p in pts if p[0] > t_hi]
    if post_peak:
        g_tr, t_tr = min(post_peak, key=lambda x: x[1])
        rec = float(recovery_bps) / 10_000.0
        if t_last > t_tr and g_last >= g_tr * (1.0 + rec):
            lines.append(
                f"Recovery: post-peak trough {g_tr:.4f} @ {_fmt_hms(t_tr)} → now {g_last:.4f} "
                f"(>={recovery_bps:.0f} bps off trough) — playbook: consider **SELL both @ bid** "
                f"if you already hold matched size (inventory required)."
            )

    return "\n".join(lines)


def _fmt_hms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0).strftime("%H:%M:%S")
