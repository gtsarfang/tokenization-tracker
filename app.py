"""Tokenization Tracker — Streamlit app.

Thin wiring only: config -> registry -> orchestrator -> viz. No business logic here.
"""

from __future__ import annotations

import sqlite3

import streamlit as st

from config import AppConfig, load_config
from reality_check import registry, viz
from reality_check.interfaces import AssetClassSource
from reality_check.models import AssetClassResult
from reality_check.orchestrator import refresh_asset_class
from reality_check.sources.prices import MarketDataReading, fetch_market_data
from reality_check.storage import get_connection, init_db

# How often live data (and the one shared CoinGecko fetch) refreshes. Kept long
# on purpose: CoinGecko's free, no-key tier has a tight rate limit, and none of
# this data moves fast enough to need refreshing more than once a day.
_REFRESH_TTL_SECONDS = 24 * 60 * 60

# Shown on the surface, not buried in the per-asset methodology expanders: a
# figure nobody can source at a glance is a figure nobody reposts. Full
# citations still live in each section's "How is this calculated?".
_SOURCES_LINE = (
    "Sources: CoinGecko · DeFiLlama · on-chain reads · World Gold Council · "
    "Silver Institute · US Treasury"
)


@st.cache_resource
def _get_connection(db_path: str) -> sqlite3.Connection:
    conn = get_connection(db_path)
    init_db(conn)
    return conn


@st.cache_data(ttl=_REFRESH_TTL_SECONDS)
def _load_market_data(config: AppConfig) -> dict[str, MarketDataReading]:
    # The one CoinGecko call the whole app makes — every source reads from this
    # shared result instead of fetching its own tokens independently.
    # Tokens with no coingecko_id have no live source at all (see
    # TokenConfig.manual_value_usd) and are excluded from this fetch entirely.
    tokens = [t for t in registry.all_tokens(config) if t.coingecko_id]
    return fetch_market_data(
        config.coingecko_base_url,
        [t.coingecko_id for t in tokens],
        {t.coingecko_id: t.fallback_price_usd for t in tokens},
        {t.coingecko_id: t.fallback_supply for t in tokens},
        config.coingecko_timeout_seconds,
        api_key=config.coingecko_api_key,
    )


@st.cache_data(ttl=_REFRESH_TTL_SECONDS)
def _load_result(name: str, _source: AssetClassSource, _conn: sqlite3.Connection) -> AssetClassResult:
    # Leading underscore on _source/_conn tells Streamlit not to hash them as part
    # of the cache key (they aren't hashable) — `name` alone is the cache key, so
    # this re-fetches live data at most once per TTL window per asset class,
    # regardless of how many times the page reruns (e.g. from toggling a radio).
    return refresh_asset_class(_source, _conn)


def main() -> None:
    st.set_page_config(page_title="Tokenization Tracker", page_icon="📊", layout="wide")

    config = load_config()
    conn = _get_connection(config.db_path)
    market_data = _load_market_data(config)
    sources = registry.get_sources(config, market_data)

    viz.inject_base_css()

    results = {name: _load_result(name, source, conn) for name, source in sources.items()}
    shared_log_span = viz.compute_shared_log_span(results.values())

    # Rendered after the data loads (unlike the old static header) because the
    # band carries the per-asset headline numbers as well as the title — it's the
    # part of the page meant to be screenshotted and posted on its own, so it
    # also carries the date and sources that make it citable in isolation.
    viz.render_hero_band(
        "Tokenization Tracker",
        "Tracking how much of each real-world asset class has moved on-chain.",
        results,
        sources_line=_SOURCES_LINE,
        url="https://github.com/gtsarfang/tokenization-tracker",
    )

    # One shared display-mode control for every card, instead of each card having
    # its own independent toggle (which let cards show inconsistent units at once).
    mode = st.segmented_control("Display as", ["%", "$", "unit"], default="%", key="global_mode")

    # Stacked full-width sections rather than a 3-per-row card grid — with only
    # three asset classes, narrow cards left a lot of empty space; a section per
    # asset uses the width for the log-scale bar instead of cramming it.
    for name, source in sources.items():
        result = results[name]
        viz.render_asset_section(
            result,
            key=name,
            methodology=source.describe_methodology(),
            quantity=source.describe_quantity(result),
            mode=mode or "%",
            shared_log_span=shared_log_span,
        )

    st.caption(
        "Informational only — not investment advice. Real-world totals are "
        "published estimates, not exact figures; see each asset class's "
        "methodology above for sources and known limitations. "
        "Open source: github.com/gtsarfang/tokenization-tracker"
    )


if __name__ == "__main__":
    main()
