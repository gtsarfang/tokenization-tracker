"""Shared CoinGecko fetcher. All sources pull from one batched `/coins/markets`
call (see `fetch_market_data`, called once app-wide in `app.py`) rather than each
making their own request — CoinGecko's free, no-key tier has a tight rate limit,
and with 8 tokens across 4 asset classes, separate per-source calls were enough
to trigger 429s and show fallback data across the board."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import requests

from reality_check.models import DataQuality


@dataclass(frozen=True)
class MarketSupply:
    total_supply: float | None
    note: str


def cross_check_note(onchain_quantity: float, market: MarketSupply, tolerance: float = 0.02) -> str:
    """Compares an on-chain supply reading against CoinGecko's reported total supply."""
    if market.total_supply is None:
        return market.note
    if onchain_quantity <= 0:
        return "cross-check skipped (zero on-chain quantity)"
    diff = abs(onchain_quantity - market.total_supply) / onchain_quantity
    if diff > tolerance:
        return f"⚠ CoinGecko-reported supply differs by {diff:.1%} from on-chain reading"
    return f"✓ matches CoinGecko-reported supply (within {diff:.1%})"


@dataclass(frozen=True)
class MarketDataReading:
    price_usd: float
    total_supply: float
    market_cap: float | None
    quality: DataQuality
    note: str


def consistency_note(reading: MarketDataReading, tolerance: float = 0.02) -> str:
    """Sanity-checks `total_supply x price` against CoinGecko's own reported
    `market_cap` from the same API response — since both figures come from the same
    source, this can't catch a wrong source, only internal inconsistency (e.g. one
    field lagging the other, or a bad response) that a single-field read wouldn't."""
    if reading.market_cap is None or reading.quality is DataQuality.FALLBACK:
        return "consistency check unavailable (no market cap in response, or using fallback)"
    implied = reading.total_supply * reading.price_usd
    if implied <= 0:
        return "consistency check skipped (zero implied value)"
    diff = abs(implied - reading.market_cap) / implied
    if diff > tolerance:
        return f"⚠ total_supply×price differs from CoinGecko's own market_cap by {diff:.1%}"
    return f"✓ total_supply×price matches CoinGecko's own market_cap (within {diff:.1%})"


def fetch_market_data(
    base_url: str,
    coingecko_ids: Sequence[str],
    fallback_prices: dict[str, float],
    fallback_supplies: dict[str, float],
    timeout_seconds: float,
    api_key: str = "",
) -> dict[str, MarketDataReading]:
    """The one CoinGecko call the whole app makes (see `app.py`), covering every
    token across every asset class in a single `/coins/markets` request — both
    on-chain-read tokens (which only need price + a cross-check figure from here)
    and aggregate-primary tokens (which need price + supply) pull from this same
    batched response, rather than each source hitting CoinGecko independently.

    `api_key`, if set (from `RC_COINGECKO_API_KEY`), uses CoinGecko's free Demo
    plan for a higher rate limit than the fully anonymous public tier — optional,
    no cost, not required for this app to function.
    """
    params: dict[str, str] = {"vs_currency": "usd", "ids": ",".join(coingecko_ids)}
    if api_key:
        params["x_cg_demo_api_key"] = api_key
    try:
        response = requests.get(f"{base_url}/coins/markets", params=params, timeout=timeout_seconds)
        response.raise_for_status()
        by_id = {row["id"]: row for row in response.json()}
    except (requests.RequestException, ValueError) as exc:
        note = f"CoinGecko request failed ({exc.__class__.__name__}); used fallback price/supply"
        return {
            coingecko_id: MarketDataReading(
                price_usd=fallback_prices[coingecko_id],
                total_supply=fallback_supplies[coingecko_id],
                market_cap=None,
                quality=DataQuality.FALLBACK,
                note=note,
            )
            for coingecko_id in coingecko_ids
        }

    readings: dict[str, MarketDataReading] = {}
    for coingecko_id in coingecko_ids:
        row = by_id.get(coingecko_id)
        price = row.get("current_price") if row else None
        supply = row.get("total_supply") if row else None
        if price is None or supply is None:
            readings[coingecko_id] = MarketDataReading(
                price_usd=fallback_prices[coingecko_id],
                total_supply=fallback_supplies[coingecko_id],
                market_cap=None,
                quality=DataQuality.FALLBACK,
                note=f"'{coingecko_id}' missing from CoinGecko response; used fallback",
            )
        else:
            market_cap = row.get("market_cap")
            readings[coingecko_id] = MarketDataReading(
                price_usd=float(price),
                total_supply=float(supply),
                market_cap=float(market_cap) if market_cap is not None else None,
                quality=DataQuality.LIVE,
                note="",
            )
    return readings
