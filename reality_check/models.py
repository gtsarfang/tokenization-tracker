"""Pure data model. No I/O, no framework imports — safe to unit test in isolation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DataQuality(str, Enum):
    LIVE = "live"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class ComponentValue:
    symbol: str
    quantity: float
    unit_price_usd: float
    value_usd: float
    supply_quality: DataQuality
    price_quality: DataQuality
    note: str = ""


@dataclass(frozen=True)
class TotalValue:
    value_usd: float
    basis_note: str
    quality: DataQuality


@dataclass(frozen=True)
class AssetClassResult:
    asset_class: str
    tokenized_usd: float
    components: tuple[ComponentValue, ...]
    total: TotalValue
    pct_tokenized: float
    as_of: datetime
    source_notes: str

    def is_stale(self) -> bool:
        if self.total.quality is DataQuality.FALLBACK:
            return True
        return any(
            c.supply_quality is DataQuality.FALLBACK
            or c.price_quality is DataQuality.FALLBACK
            for c in self.components
        )
