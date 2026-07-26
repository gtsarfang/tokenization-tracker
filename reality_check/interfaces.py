"""The extensibility contract every asset-class data source must satisfy.

Adding a new asset class (Treasuries, real estate, ...) means writing one module
that implements this Protocol, adding one config entry, and registering it in
`reality_check.registry` — no changes to calc.py, storage.py, or viz.py.
"""

from __future__ import annotations

from typing import Protocol

from reality_check.models import AssetClassResult, ComponentValue, TotalValue


class AssetClassSource(Protocol):
    asset_class: str

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        """Fetch on-chain/tokenized components. Must never raise; internally falls
        back to configured manual values and marks the affected fields as stale."""
        ...

    def fetch_total(self) -> TotalValue:
        """Fetch/derive the real-world total. Must never raise; internally falls
        back to configured manual values and marks the result as stale."""
        ...

    def describe_methodology(self) -> str:
        """Static markdown explaining how tokenized/total are computed for this
        asset class, with source citations. Never raises; no network/IO."""
        ...

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str] | None:
        """Optional physical-unit readout as (tokenized, total) display strings,
        e.g. ("55 t", "216,265 t") for a commodity measured by weight. Return None
        if this asset class has no natural physical unit (e.g. Treasuries)."""
        ...
