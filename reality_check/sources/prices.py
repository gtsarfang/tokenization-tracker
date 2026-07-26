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
