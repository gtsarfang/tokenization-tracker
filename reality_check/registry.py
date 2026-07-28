"""Maps asset-class slugs to their data source instance.

Adding a new asset class: implement AssetClassSource in a new sources/<name>.py
module, then add one line here.
"""

from __future__ import annotations

from config import AppConfig, TokenConfig
from reality_check.interfaces import AssetClassSource
from reality_check.sources.gold import GoldSource
from reality_check.sources.prices import MarketDataReading
from reality_check.sources.silver import SilverSource
from reality_check.sources.treasuries import TreasurySource


def get_sources(
    config: AppConfig, market_data: dict[str, MarketDataReading]
) -> dict[str, AssetClassSource]:
    # Order is display order (dicts preserve insertion order and the UI renders
    # them in sequence). Gold and silver lead because their coverage is the most
    # complete; Treasuries sits last while its component list is still filling in.
    return {
        "gold": GoldSource(config, market_data),
        "silver": SilverSource(config, market_data),
        "treasuries": TreasurySource(config, market_data),
    }


def all_tokens(config: AppConfig) -> list[TokenConfig]:
    """Every TokenConfig across every asset class, for the one shared batched
    CoinGecko fetch (see `app.py`)."""
    token_groups = (
        config.gold.tokens,
        config.silver.tokens,
        config.treasuries.tokens,
    )
    return [token for tokens in token_groups for token in tokens]
