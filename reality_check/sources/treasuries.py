"""Treasuries asset-class source: BUIDL + USDY tokenized supply vs. total US
marketable Treasury debt (Debt Held by the Public).

Unlike gold's above-ground stock (a slowly-changing figure, refreshed periodically
from World Gold Council data), the Treasury debt total is fetched live from the US
Treasury's own public API — it changes daily, so a static constant would drift too
fast to be a meaningful denominator. See `_fetch_debt_held_by_public`.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from config import AppConfig
from reality_check.models import AssetClassResult, ComponentValue, DataQuality, TotalValue
from reality_check.sources.defillama import fetch_protocol_tvl
from reality_check.sources.prices import MarketDataReading, consistency_note, fetch_market_data

_DEBT_TO_PENNY_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny"
)


@dataclass(frozen=True)
class _DebtReading:
    value_usd: float
    quality: DataQuality
    note: str


def _fetch_debt_held_by_public(timeout_seconds: float, fallback_value_usd: float) -> _DebtReading:
    try:
        response = requests.get(
            _DEBT_TO_PENNY_URL,
            params={"sort": "-record_date", "page[size]": 1},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        row = response.json()["data"][0]
        return _DebtReading(
            value_usd=float(row["debt_held_public_amt"]),
            quality=DataQuality.LIVE,
            note=f"live as of {row['record_date']}",
        )
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        return _DebtReading(
            value_usd=fallback_value_usd,
            quality=DataQuality.FALLBACK,
            note=f"Treasury Fiscal Data API request failed ({exc.__class__.__name__}); used fallback",
        )


class TreasurySource:
    asset_class: str = "treasuries"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._market_cache: dict[str, MarketDataReading] | None = None

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        market = self._get_market_data()

        components = []
        for token in self._config.treasuries.tokens:
            reading = market[token.coingecko_id]
            coingecko_value_usd = reading.total_supply * reading.price_usd

            value_usd = coingecko_value_usd
            quality = reading.quality
            notes = [reading.note, consistency_note(reading)]

            if token.defillama_slug:
                defillama_reading = fetch_protocol_tvl(
                    token.defillama_slug, self._config.coingecko_timeout_seconds
                )
                if defillama_reading.value_usd is not None:
                    # DefiLlama sums TVL per deployment chain; verified this is
                    # more complete than CoinGecko's total_supply for BUIDL/USDY
                    # specifically (CoinGecko was found to undercount even after
                    # switching away from a single-chain on-chain read), so
                    # DefiLlama's figure is used as the primary value when
                    # available, not just as a cross-check.
                    diff = abs(coingecko_value_usd - defillama_reading.value_usd) / defillama_reading.value_usd
                    value_usd = defillama_reading.value_usd
                    quality = DataQuality.LIVE
                    notes.append(
                        f"primary source: DefiLlama TVL (${defillama_reading.value_usd / 1e9:.2f}B); "
                        f"CoinGecko total_supply×price (${coingecko_value_usd / 1e9:.2f}B) "
                        f"differs by {diff:.1%}"
                    )
                else:
                    notes.append(defillama_reading.note)

            quantity = value_usd / reading.price_usd if reading.price_usd else 0.0
            components.append(
                ComponentValue(
                    symbol=token.symbol,
                    quantity=quantity,
                    unit_price_usd=reading.price_usd,
                    value_usd=value_usd,
                    supply_quality=quality,
                    price_quality=reading.quality,
                    note="; ".join(n for n in notes if n),
                    display_name=f"{token.issuer} {token.symbol}",
                    backing=token.backing,
                )
            )
        return tuple(components)

    def fetch_total(self) -> TotalValue:
        treasuries = self._config.treasuries
        debt = _fetch_debt_held_by_public(
            self._config.coingecko_timeout_seconds, treasuries.fallback_total_debt_usd
        )
        basis_note = f"{treasuries.source_citation} ({debt.note})"
        return TotalValue(value_usd=debt.value_usd, basis_note=basis_note, quality=debt.quality)

    def describe_methodology(self) -> str:
        treasuries = self._config.treasuries
        symbols = " + ".join(token.symbol for token in treasuries.tokens)
        return (
            f"**Tokenized value** — {symbols} are natively minted independently "
            "on multiple chains (BUIDL on 8, USDY on 12), each with its own "
            "separate supply — there is no single canonical chain whose "
            "`totalSupply()` represents the global total, so a single-chain "
            "on-chain read would meaningfully undercount them (confirmed: this "
            "app's first implementation did exactly that). The fix wasn't as "
            "simple as switching to CoinGecko's `total_supply`, either — "
            "checking DefiLlama's per-chain TVL breakdown for the same tokens "
            "showed CoinGecko *also* undercounts both (by ~30% for BUIDL, ~19% "
            "for USDY, as of 2026-07-26), apparently not aggregating every "
            "deployment chain either. DefiLlama's TVL (an explicit sum across "
            "every chain it tracks the protocol on) is used as the primary "
            "value when available; CoinGecko's `total_supply × current_price` "
            "is kept as a fallback and shown for comparison.\n\n"
            f"**Why only {symbols}?** BlackRock's BUIDL and Ondo's USDY are two of "
            "the largest tokenized US Treasury products. Circle's USYC is currently "
            "comparable in size or larger but isn't included yet — a candidate for "
            "a future addition, not excluded on principle. This means the true "
            "tokenized total is an undercount, never an overcount.\n\n"
            "**Is summing them correct — any overlap?** No double-counting: BUIDL "
            "(BlackRock, via Securitize) and USDY (Ondo) are independently managed "
            "funds holding their own short-term Treasury instruments, not wrapped "
            "or derivative versions of each other or of a shared pool.\n\n"
            "**Total Treasury debt** — fetched live from the US Treasury's own "
            "Fiscal Data API (`debt_to_penny`), using 'Debt Held by the Public' "
            "(total public debt minus intragovernmental holdings) as the closest "
            "live, daily-updated proxy for total marketable Treasury debt. Unlike "
            "gold's above-ground stock, this changes daily, so it's fetched fresh "
            "on every refresh rather than stored as a periodically-updated "
            "constant.\n\n"
            "Any value that falls back to a manually configured constant (CoinGecko, "
            "DefiLlama, or Treasury API failure) is marked stale — see the badge "
            "above if so.\n\n"
            "**Verification** — DefiLlama and CoinGecko are independent data "
            "providers, so using DefiLlama as primary and comparing it against "
            "CoinGecko's own `total_supply × price` is a genuine cross-source "
            "check, not a same-source consistency check like Silver/Private "
            "Credit get. `total_supply × price` is also checked against "
            "CoinGecko's own reported `market_cap` from the same API response, "
            "for internal consistency on the fallback path."
        )

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str] | None:
        return None  # no natural physical unit for Treasuries

    def _get_market_data(self) -> dict[str, MarketDataReading]:
        if self._market_cache is None:
            treasuries = self._config.treasuries
            coingecko_ids = [token.coingecko_id for token in treasuries.tokens]
            fallback_prices = {t.coingecko_id: t.fallback_price_usd for t in treasuries.tokens}
            fallback_supplies = {t.coingecko_id: t.fallback_supply for t in treasuries.tokens}
            self._market_cache = fetch_market_data(
                self._config.coingecko_base_url,
                coingecko_ids,
                fallback_prices,
                fallback_supplies,
                self._config.coingecko_timeout_seconds,
            )
        return self._market_cache
