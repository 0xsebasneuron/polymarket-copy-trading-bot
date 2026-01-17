from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class BookLevelRow:
    price: str
    size: str

    def to_camel_dict(self) -> dict[str, Any]:
        return {"price": self.price, "size": self.size}


@dataclass
class BtcOrderbookUpdate:
    slug: str
    question: str
    asset_id: str
    down_asset_id: Optional[str]
    best_bid: Optional[float]
    best_ask: Optional[float]
    mid: Optional[float]
    bids: list[BookLevelRow]
    asks: list[BookLevelRow]
    updated_at_ms: int
    down_best_bid: Optional[float] = None
    down_best_ask: Optional[float] = None
    down_mid: Optional[float] = None
    down_bids: list[BookLevelRow] = field(default_factory=list)
    down_asks: list[BookLevelRow] = field(default_factory=list)

    def to_camel_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {
            "slug": d["slug"],
            "question": d["question"],
            "assetId": d["asset_id"],
            "downAssetId": d["down_asset_id"],
            "bestBid": d["best_bid"],
            "bestAsk": d["best_ask"],
            "mid": d["mid"],
            "bids": [x.to_camel_dict() for x in self.bids],
            "asks": [x.to_camel_dict() for x in self.asks],
            "updatedAtMs": d["updated_at_ms"],
            "downBestBid": d["down_best_bid"],
            "downBestAsk": d["down_best_ask"],
            "downMid": d["down_mid"],
            "downBids": [x.to_camel_dict() for x in self.down_bids],
            "downAsks": [x.to_camel_dict() for x in self.down_asks],
        }


@dataclass
class BtcMarketSwitch:
    from_slug: Optional[str]
    to_slug: str
    reason: str

    def to_camel_dict(self) -> dict[str, Any]:
        return {
            "fromSlug": self.from_slug,
            "toSlug": self.to_slug,
            "reason": self.reason,
        }
