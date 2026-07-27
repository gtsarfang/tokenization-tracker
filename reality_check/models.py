"""Pure data model. No I/O, no framework imports — safe to unit test in isolation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DataQuality(str, Enum):
    LIVE = "live"
    FALLBACK = "fallback"
    # A figure with no live source at all (see TokenConfig.manual_value_usd) —
    # deliberately, permanently manual rather than a live call that happened to
    # fail. Distinct from FALLBACK so the UI can label it "manually tracked"
    # instead of the "stale" badge implying a transient outage.
    MANUAL = "manual"


@dataclass(frozen=True)
class ComponentValue:
    symbol: str
    quantity: float
    unit_price_usd: float
    value_usd: float
    supply_quality: DataQuality
    price_quality: DataQuality
    note: str = ""
    # Human-readable label (e.g. "BlackRock BUIDL") for display where a bare ticker
    # wouldn't mean anything to someone unfamiliar with it. Falls back to `symbol`
    # wherever left blank.
    display_name: str = ""
    # Plain-English description of the real-world collateral this token represents
    # (e.g. "1 troy oz of allocated gold in a Swiss vault") — the point of this app
    # is what backs a token, not just its price.
    backing: str = ""


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
    # Optional narrower denominator (e.g. gold/silver's "identifiable investment
    # stock" — bars/coins/ETFs — vs. `total`'s all-uses figure including
    # jewelry/industrial/reserves). None for asset classes where no meaningfully
    # different denominator exists (e.g. Treasuries — the debt total is already
    # the relevant liquid figure).
    alt_total: TotalValue | None = None
    alt_pct_tokenized: float | None = None

    def is_stale(self) -> bool:
        # MANUAL is excluded on purpose: it's a deliberate, permanent choice
        # (no live source exists), not a live call that failed — the UI labels
        # those components "manually tracked" instead of raising the "stale"
        # badge, which should mean "this normally-live figure is out of date."
        if self.total.quality is DataQuality.FALLBACK:
            return True
        return any(
            c.supply_quality is DataQuality.FALLBACK
            or c.price_quality is DataQuality.FALLBACK
            for c in self.components
        )

    def has_manual_components(self) -> bool:
        return any(
            c.supply_quality is DataQuality.MANUAL or c.price_quality is DataQuality.MANUAL
            for c in self.components
        )
