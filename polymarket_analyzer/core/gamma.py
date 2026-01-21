from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

GAMMA_MARKET_SLUG_URL = "https://gamma-api.polymarket.com/markets/slug/{slug}"


def floor_interval_epoch_sec(now_sec: int, interval_minutes: int) -> int:
    step = max(1, interval_minutes) * 60
    return now_sec - (now_sec % step)


def candidate_slugs(symbol: str, now_sec: int, interval_minutes: int) -> list[str]:
    step = max(1, interval_minutes) * 60
    base = floor_interval_epoch_sec(now_sec, interval_minutes)
    sym = symbol.strip().lower()
    slugs: list[str] = []
    for k in range(0, 13):
        slugs.append(f"{sym}-updown-{interval_minutes}m-{base + k * step}")
        if k != 0:
            slugs.append(f"{sym}-updown-{interval_minutes}m-{base - k * step}")
    return slugs


def _coerce_json_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    return []


def assign_up_down_tokens_from_gamma_market(payload: dict[str, Any]) -> tuple[str, Optional[str]]:
    """
    Map ``clobTokenIds`` to UP vs DOWN using Gamma ``outcomes`` order/labels when present.

    Falls back to index ``[0], [1]`` if outcomes are missing or ambiguous.
    """
    token_ids_raw = payload.get("clobTokenIds")
    if not isinstance(token_ids_raw, str):
        raise ValueError("missing clobTokenIds")
    token_ids: list[str] = [str(x) for x in json.loads(token_ids_raw)]
    if not token_ids:
        raise ValueError("clobTokenIds empty")
    if len(token_ids) == 1:
        return token_ids[0], None

    outcomes = _coerce_json_list(payload.get("outcomes"))
    labels = [str(x).strip().lower() for x in outcomes] if outcomes else []

    def idx_for(*needles: str) -> Optional[int]:
        """Match outcome labels to needles; avoid short-substring false positives (e.g. ``\"up\" in \"down\"``)."""
        for i, lab in enumerate(labels):
            for n in needles:
                if not n:
                    continue
                if lab == n:
                    return i
                # Only allow substring for longer needles so "up" does not match inside "down".
                if len(n) > 3 and n in lab:
                    return i
        return None

    i_up = idx_for("up") if labels else None
    i_dn = idx_for("down") if labels else None
    if i_up is None:
        i_up = idx_for("yes", "higher", "above")
    if i_dn is None:
        i_dn = idx_for("no", "lower", "below")

    n = len(token_ids)

    def other_index(i: int) -> int:
        for j in range(n):
            if j != i:
                return j
        return 0

    if i_up is not None and i_dn is not None and i_up < n and i_dn < n and i_up != i_dn:
        return token_ids[i_up], token_ids[i_dn]
    if i_up is not None and i_up < n:
        j = other_index(i_up)
        return token_ids[i_up], token_ids[j]
    if i_dn is not None and i_dn < n:
        j = other_index(i_dn)
        return token_ids[j], token_ids[i_dn]
    return token_ids[0], token_ids[1] if len(token_ids) > 1 else None


async def resolve_market_asset_ids(
    client: httpx.AsyncClient,
    symbol: str,
    interval_minutes: int,
) -> tuple[str, str, str, Optional[str]]:
    now_sec = int(time.time())
    sym = symbol.strip().lower()
    if not sym:
        raise ValueError("market symbol is empty")

    for slug in candidate_slugs(sym, now_sec, interval_minutes):
        url = GAMMA_MARKET_SLUG_URL.format(slug=slug)
        resp = await client.get(url)
        if resp.status_code != 200:
            continue
        v: dict[str, Any] = resp.json()

        active = bool(v.get("active", False))
        closed = bool(v.get("closed", False))
        if not active or closed:
            continue

        question = str(v.get("question") or symbol)
        up_token, down_token = assign_up_down_tokens_from_gamma_market(v)
        return slug, question, up_token, down_token

    raise LookupError(
        f"could not resolve an active {sym}-updown-{interval_minutes}m-* market slug"
    )
