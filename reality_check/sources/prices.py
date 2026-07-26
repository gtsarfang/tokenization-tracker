"""Shared CoinGecko price fetcher. Reusable by any future asset-class source that
prices a token via the free `/simple/price` endpoint."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import requests

from reality_check.models import DataQuality


@dataclass(frozen=True)
class PriceReading:
    price_usd: float
    quality: DataQuality
    note: str


@dataclass(frozen=True)
class MarketSupply:
    total_supply: float | None
    note: str


def fetch_cross_check_supply(
    base_url: str,
    coingecko_ids: Sequence[str],
    timeout_seconds: float,
) -> dict[str, MarketSupply]:
    """Best-effort secondary supply reading from CoinGecko's `/coins/markets` endpoint,
    used only to sanity-check the primary on-chain `totalSupply()` reading — an
    on-chain read is already the ground truth for a specific contract, so this never
    blocks or replaces the primary value, only flags if the two disagree by more than
    expected (e.g. a wrong contract address or decimals bug)."""
    try:
        response = requests.get(
            f"{base_url}/coins/markets",
            params={"vs_currency": "usd", "ids": ",".join(coingecko_ids)},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError):
        return {
            coingecko_id: MarketSupply(None, "cross-check unavailable (CoinGecko request failed)")
            for coingecko_id in coingecko_ids
        }

    by_id = {row["id"]: row for row in rows}
    readings: dict[str, MarketSupply] = {}
    for coingecko_id in coingecko_ids:
        row = by_id.get(coingecko_id)
        total_supply = row.get("total_supply") if row else None
        if total_supply is None:
            readings[coingecko_id] = MarketSupply(None, "cross-check unavailable (no data)")
        else:
            readings[coingecko_id] = MarketSupply(float(total_supply), "")
    return readings


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
) -> dict[str, MarketDataReading]:
    """Primary price+supply source (via `/coins/markets`) for tokens natively minted
    on multiple chains with independent per-chain supply (e.g. USDY, BUIDL) — for
    those, a single-chain on-chain `totalSupply()` read would meaningfully undercount,
    since there's no single canonical chain holding the full circulating supply.
    CoinGecko aggregates `total_supply` across every chain it tracks for a coin id."""
    try:
        response = requests.get(
            f"{base_url}/coins/markets",
            params={"vs_currency": "usd", "ids": ",".join(coingecko_ids)},
            timeout=timeout_seconds,
        )
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


def fetch_simple_prices(
    base_url: str,
    coingecko_ids: Sequence[str],
    fallback_prices: dict[str, float],
    timeout_seconds: float,
) -> dict[str, PriceReading]:
    """Fetches USD prices for `coingecko_ids` in a single request.

    Falls back per-id (not all-or-nothing): if the whole request fails, every id
    falls back to `fallback_prices`; if only some ids are missing from the response,
    only those ids fall back.
    """
    try:
        response = requests.get(
            f"{base_url}/simple/price",
            params={"ids": ",".join(coingecko_ids), "vs_currencies": "usd"},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        note = f"CoinGecko request failed ({exc.__class__.__name__}); used fallback price"
        return {
            coingecko_id: PriceReading(
                price_usd=fallback_prices[coingecko_id],
                quality=DataQuality.FALLBACK,
                note=note,
            )
            for coingecko_id in coingecko_ids
        }

    readings: dict[str, PriceReading] = {}
    for coingecko_id in coingecko_ids:
        price = payload.get(coingecko_id, {}).get("usd")
        if price is None:
            readings[coingecko_id] = PriceReading(
                price_usd=fallback_prices[coingecko_id],
                quality=DataQuality.FALLBACK,
                note=f"'{coingecko_id}' missing from CoinGecko response; used fallback price",
            )
        else:
            readings[coingecko_id] = PriceReading(
                price_usd=float(price), quality=DataQuality.LIVE, note=""
            )
    return readings
