"""Maps asset-class slugs to their data source instance.

Adding a new asset class: implement AssetClassSource in a new sources/<name>.py
module, then add one line here.
"""

from __future__ import annotations

from config import AppConfig
from reality_check.interfaces import AssetClassSource
from reality_check.sources.gold import GoldSource
from reality_check.sources.treasuries import TreasurySource


def get_sources(config: AppConfig) -> dict[str, AssetClassSource]:
    return {"gold": GoldSource(config), "treasuries": TreasurySource(config)}
