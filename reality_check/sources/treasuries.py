"""Treasuries asset-class source: BUIDL + USDY + USYC tokenized supply vs. total
US marketable Treasury debt (Debt Held by the Public).

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
from reality_check.sources.prices import MarketDataReading, consistency_note

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

    def __init__(self, config: AppConfig, market_data: dict[str, MarketDataReading]) -> None:
        self._config = config
        self._market_data = market_data

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        market = self._market_data

        components = []
        for token in self._config.treasuries.tokens:
            reading = market[token.coingecko_id]
            value_usd = reading.total_supply * reading.price_usd
            notes = [reading.note, consistency_note(reading)]

            if token.defillama_slug:
                defillama_reading = fetch_protocol_tvl(
                    token.defillama_slug, self._config.coingecko_timeout_seconds
                )
                if defillama_reading.value_usd is not None:
                    # DefiLlama sums per-chain token balances, which double-counts
                    # value moved via a lock-and-mint bridge (BUIDL uses Wormhole:
                    # locked on the source chain *and* minted on the destination
                    # chain, both counted). A third source (rwa.xyz, which tracks
                    # net issuance) confirmed CoinGecko is the accurate one here —
                    # DefiLlama is kept only as an informational comparison, not
                    # used as primary (a prior version of this code did use it as
                    # primary, based on a two-source comparison that wrongly
                    # assumed the larger number was more complete).
                    diff = (
                        abs(value_usd - defillama_reading.value_usd) / value_usd if value_usd else 0.0
                    )
                    notes.append(
                        f"DefiLlama TVL (${defillama_reading.value_usd / 1e9:.2f}B) differs by "
                        f"{diff:.1%} — likely double-counts bridged supply, not used as primary"
                    )
                else:
                    notes.append(defillama_reading.note)

            components.append(
                ComponentValue(
                    symbol=token.symbol,
                    quantity=reading.total_supply,
                    unit_price_usd=reading.price_usd,
                    value_usd=value_usd,
                    supply_quality=reading.quality,
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

    def fetch_alt_total(self) -> TotalValue | None:
        # Unlike gold/silver's total (which mixes illiquid jewelry/reserves in
        # with investable bars/coins/ETFs), "Debt Held by the Public" is already
        # the marketable, liquid figure — there's no meaningfully narrower
        # subset to compare against, so no alternate denominator here.
        return None

    def describe_methodology(self) -> str:
        treasuries = self._config.treasuries
        symbols = " + ".join(token.symbol for token in treasuries.tokens)
        return (
            f"**Tokenized value** — fetched live from CoinGecko's "
            "`/coins/markets` endpoint (`total_supply × current_price`), *not* "
            f"read from a single on-chain contract like gold's PAXG/XAUT. "
            f"{symbols} are natively minted independently on multiple chains "
            "(BUIDL on 8, USDY on 12), each with its own separate supply — "
            "there is no single canonical chain whose `totalSupply()` "
            "represents the global total, so a single-chain on-chain read "
            "would meaningfully undercount them (confirmed: this app's first "
            "implementation did exactly that).\n\n"
            "**A second, corrected fix** — checking DefiLlama's per-chain TVL "
            "breakdown initially looked like it revealed CoinGecko *also* "
            "undercounting both tokens, so an earlier version of this app "
            "switched to DefiLlama as primary. That was wrong: DefiLlama sums "
            "per-chain token balances, and BUIDL moves across chains via "
            "Wormhole's lock-and-mint bridge — locked on the source chain *and* "
            "minted on the destination chain, both counted, inflating the sum. "
            "A third source, [rwa.xyz](https://rwa.xyz) (which tracks net "
            "issuance, not per-chain balances), confirmed CoinGecko's figure "
            "was right all along for both BUIDL and USDY. Two independent "
            "sources agreeing beats trusting the larger of two numbers.\n\n"
            f"**Why {symbols}?** BlackRock's BUIDL, Ondo's USDY, Circle's USYC "
            "(Hashnote's US Yield Coin), Janus Henderson's JTRSY (issued via "
            "Centrifuge), Superstate's USTB (distributed with Invesco), Ondo's "
            "OUSG, and WisdomTree's WTGXX are the tokenized US Treasury "
            "products confirmed clean so far. Franklin Templeton's BENJI/"
            "iBENJI and JPMorgan's JLTXX are bigger gaps still but have no "
            "trustworthy live-fetchable source (see README) — this means the "
            "true tokenized total is an undercount, never an overcount.\n\n"
            "**Is summing them correct — any overlap?** No double-counting: "
            "all seven are independently managed funds/vehicles holding their "
            "own short-term Treasury bills and repo positions, not wrapped or "
            "derivative versions of each other or of a shared pool.\n\n"
            "**Total Treasury debt** — fetched live from the US Treasury's own "
            "Fiscal Data API (`debt_to_penny`), using 'Debt Held by the Public' "
            "(total public debt minus intragovernmental holdings) as the closest "
            "live, daily-updated proxy for total marketable Treasury debt. Unlike "
            "gold's above-ground stock, this changes daily, so it's fetched fresh "
            "on every refresh rather than stored as a periodically-updated "
            "constant.\n\n"
            "Any value that falls back to a manually configured constant (CoinGecko "
            "or Treasury API failure) is marked stale — see the badge above if so.\n\n"
            "**Verification** — `total_supply × price` is checked against "
            "CoinGecko's own reported `market_cap` from the same API response "
            "(internal consistency). DefiLlama's TVL is also shown for "
            "comparison but isn't used to judge correctness, since it's known to "
            "run high for lock-and-mint bridged tokens like BUIDL — a one-off "
            "manual check against rwa.xyz (not wired in live — no free API) is "
            "what actually settled which source to trust."
        )

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str] | None:
        return None  # no natural physical unit for Treasuries
