"""Pure calculation logic. No network, no database, no Streamlit — the entire unit-test surface."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from reality_check.models import AssetClassResult, ComponentValue, TotalValue


def compute_pct_tokenized(tokenized_usd: float | None, total_usd: float | None) -> float:
    """Percentage of total_usd represented by tokenized_usd, clamped to [0, 100].

    Never raises: missing inputs, a non-positive total, or a negative tokenized
    value all resolve to 0.0 rather than propagating an error or a nonsensical ratio.
    A tokenized value that (due to stale/mismatched data) exceeds the total is
    clamped to 100.0 rather than reported as e.g. 150%.
    """
    if tokenized_usd is None or total_usd is None:
        return 0.0
    if total_usd <= 0:
        return 0.0
    if tokenized_usd < 0:
        return 0.0
    pct = (tokenized_usd / total_usd) * 100
    return min(pct, 100.0)


def sum_component_values(components: Iterable[ComponentValue]) -> float:
    return sum(c.value_usd for c in components)


def build_asset_class_result(
    asset_class: str,
    components: tuple[ComponentValue, ...],
    total: TotalValue,
    as_of: datetime,
    source_notes: str,
    alt_total: TotalValue | None = None,
) -> AssetClassResult:
    tokenized_usd = sum_component_values(components)
    pct_tokenized = compute_pct_tokenized(tokenized_usd, total.value_usd)
    alt_pct_tokenized = (
        compute_pct_tokenized(tokenized_usd, alt_total.value_usd) if alt_total else None
    )
    return AssetClassResult(
        asset_class=asset_class,
        tokenized_usd=tokenized_usd,
        components=components,
        total=total,
        pct_tokenized=pct_tokenized,
        as_of=as_of,
        source_notes=source_notes,
        alt_total=alt_total,
        alt_pct_tokenized=alt_pct_tokenized,
    )
