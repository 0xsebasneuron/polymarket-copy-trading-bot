from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from polymarket_analyzer.core.models import BookLevelRow


def as_float_from_json(v: object) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def level_to_price_size(level: object) -> Optional[tuple[float, float]]:
    if isinstance(level, dict):
        p_raw = level.get("price")
        s_raw = level.get("size")
        p = as_float_from_json(p_raw) if p_raw is not None else None
        if p is None:
            return None
        s = as_float_from_json(s_raw) if s_raw is not None else 0.0
        return p, s or 0.0
    if isinstance(level, list) and len(level) >= 2:
        p = as_float_from_json(level[0])
        if p is None:
            return None
        s = as_float_from_json(level[1]) if len(level) > 1 else 0.0
        return p, s or 0.0
    return None


def normalize_price_key(price: str) -> str:
    p = price.strip()
    try:
        x = float(p)
        return f"{x:.6f}"
    except ValueError:
        return p


def parse_price_key(key: str) -> Optional[float]:
    try:
        return float(key)
    except ValueError:
        return None


class SideBook:
    """price_key -> size (stable sort via normalized string keys)."""

    def __init__(self) -> None:
        self.levels: OrderedDict[str, float] = OrderedDict()

    def set_level(self, price: str, size: float) -> None:
        p = normalize_price_key(price)
        if size <= 0.0:
            self.levels.pop(p, None)
        else:
            self.levels[p] = size

    def replace_from_book_array(self, levels: list[object]) -> None:
        self.levels.clear()
        for lvl in levels:
            parsed = level_to_price_size(lvl)
            if not parsed:
                continue
            pr, sz = parsed
            if sz > 0.0:
                self.levels[normalize_price_key(str(pr))] = sz

    def _sorted_keys_desc(self) -> list[str]:
        return sorted(self.levels.keys(), key=lambda k: parse_price_key(k) or 0.0, reverse=True)

    def _sorted_keys_asc(self) -> list[str]:
        return sorted(self.levels.keys(), key=lambda k: parse_price_key(k) or 0.0)

    def top_n_desc(self, n: int) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for k in self._sorted_keys_desc()[:n]:
            out.append((k, self.levels[k]))
        return out

    def top_n_asc(self, n: int) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for k in self._sorted_keys_asc()[:n]:
            out.append((k, self.levels[k]))
        return out

    def best_price_desc(self) -> Optional[float]:
        for k in self._sorted_keys_desc():
            if self.levels.get(k, 0) > 0.0:
                return parse_price_key(k)
        return None

    def best_price_asc(self) -> Optional[float]:
        for k in self._sorted_keys_asc():
            if self.levels.get(k, 0) > 0.0:
                return parse_price_key(k)
        return None

    def best_price_size_desc(self) -> Optional[tuple[float, float]]:
        """Best bid side (highest buy): (price, size)."""
        for k in self._sorted_keys_desc():
            s = self.levels.get(k, 0.0)
            if s > 0.0:
                p = parse_price_key(k)
                if p is not None:
                    return p, s
        return None

    def best_price_size_asc(self) -> Optional[tuple[float, float]]:
        """Best ask side (lowest sell): (price, size)."""
        for k in self._sorted_keys_asc():
            s = self.levels.get(k, 0.0)
            if s > 0.0:
                p = parse_price_key(k)
                if p is not None:
                    return p, s
        return None


class OrderBook:
    def __init__(self) -> None:
        self.bids = SideBook()
        self.asks = SideBook()

    def best_bid_with_size(self) -> Optional[tuple[float, float]]:
        return self.bids.best_price_size_desc()

    def best_ask_with_size(self) -> Optional[tuple[float, float]]:
        return self.asks.best_price_size_asc()

    def top_rows_for_emit(self) -> tuple[list[BookLevelRow], list[BookLevelRow], Optional[float], Optional[float], Optional[float]]:
        best_bid = self.bids.best_price_desc()
        best_ask = self.asks.best_price_asc()
        mid: Optional[float] = None
        if best_bid is not None and best_ask is not None and best_ask > 0.0 and best_bid > 0.0:
            mid = (best_ask + best_bid) / 2.0

        bids = [
            BookLevelRow(price=p, size=f"{s:.4f}")
            for p, s in self.bids.top_n_desc(12)
        ]
        asks = [
            BookLevelRow(price=p, size=f"{s:.4f}")
            for p, s in self.asks.top_n_asc(12)
        ]
        return bids, asks, best_bid, best_ask, mid
