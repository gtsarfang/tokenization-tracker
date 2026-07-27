"""Silver asset-class source: KAG tokenized supply vs. total above-ground silver
value. Kinesis Silver (KAG) is the dominant tokenized silver product by a wide
margin, unlike gold's PAXG+XAUT pair — so there's just one component here.

KAG is natively minted on Kinesis's own ledger (a Stellar fork); the Ethereum
ERC-20 contract is only a secondary "wrapped" representation holding a small
fraction of total supply — same underlying issue as Treasuries' BUIDL/USDY, so
this uses the same CoinGecko-aggregate-as-primary-source pattern as
`treasuries.py`, not a direct on-chain read like gold.py.
"""

from __future__ import annotations

from config import TROY_OZ_PER_TONNE, AppConfig, format_tonnes
from reality_check.models import AssetClassResult, ComponentValue, TotalValue
from reality_check.sources.prices import MarketDataReading, consistency_note, fetch_market_data


class SilverSource:
    asset_class: str = "silver"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._market_cache: dict[str, MarketDataReading] | None = None

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        market = self._get_market_data()

        components = []
        for token in self._config.silver.tokens:
            reading = market[token.coingecko_id]
            check = consistency_note(reading)
            components.append(
                ComponentValue(
                    symbol=token.symbol,
                    quantity=reading.total_supply,
                    unit_price_usd=reading.price_usd,
                    value_usd=reading.total_supply * reading.price_usd,
                    supply_quality=reading.quality,
                    price_quality=reading.quality,
                    note="; ".join(n for n in (reading.note, check) if n),
                    display_name=f"{token.issuer} {token.symbol}",
                    backing=token.backing,
                )
            )
        return tuple(components)

    def fetch_total(self) -> TotalValue:
        silver = self._config.silver
        token = silver.tokens[0]
        spot = self._get_market_data()[token.coingecko_id]
        total_usd = silver.total_tonnes * TROY_OZ_PER_TONNE * spot.price_usd
        basis_note = (
            f"{silver.total_tonnes:,.0f} t ({silver.source_citation}) "
            f"@ ${spot.price_usd:,.2f}/oz (KAG proxy, {spot.quality.value})"
        )
        return TotalValue(value_usd=total_usd, basis_note=basis_note, quality=spot.quality)

    def describe_methodology(self) -> str:
        silver = self._config.silver
        token = silver.tokens[0]
        return (
            f"**Tokenized supply & price** — fetched live from CoinGecko's "
            "`/coins/markets` endpoint (`total_supply × current_price`), *not* "
            f"read from the {token.symbol} Ethereum contract. {token.symbol} is "
            "natively minted on Kinesis's own ledger (a Stellar fork); the "
            "Ethereum ERC-20 contract is only a secondary 'wrapped' "
            "representation holding a small fraction of total supply — the same "
            "kind of issue as Treasuries' BUIDL/USDY, so the same fix applies: "
            "use the aggregator's total instead of a single-chain on-chain read.\n\n"
            f"**Why only {token.symbol}?** Kinesis Silver is the dominant "
            "tokenized silver product by a wide margin — no second silver token "
            "is large enough yet to be worth including, unlike gold's PAXG+XAUT "
            "pair. This means the true tokenized total is an undercount, never "
            "an overcount.\n\n"
            f"**Silver spot price** — derived from {token.symbol}'s market price "
            "rather than a separate metals API, since it's redeemable 1:1 for a "
            "troy ounce of allocated silver.\n\n"
            "**Total silver value** — this is far murkier than gold's. The Silver "
            "Institute's 'identifiable above-ground stocks' (investment bars/coins "
            "only) is about 20x smaller than broader estimates that include "
            "jewelry, silverware, and industrial stock. To stay comparable with "
            "gold's WGC figure (which *does* include jewelry and industrial "
            f"holdings), this uses the broader estimate: {silver.source_citation}, "
            f"{silver.total_tonnes:,.0f} t total.\n\n"
            "Any value that falls back to a manually configured constant "
            "(CoinGecko failure) is marked stale — see the badge above if so.\n\n"
            "**Verification** — like Treasuries, there's no independent on-chain "
            "figure to cross-check against (CoinGecko's aggregate *is* the primary "
            "source). Instead, `total_supply × price` is checked against "
            "CoinGecko's own reported `market_cap` from the same API response — "
            "this can't catch a wrong source, only an internally inconsistent one. "
            "DefiLlama (used as a genuine second source for gold and Treasuries) "
            "was checked but has no entry that clearly tracks Kinesis Silver "
            "specifically as of 2026-07-26 — its 'Kinesis Labs' listing is an "
            "unrelated protocol, not Kinesis Money. A manual spot-check against "
            "CoinMarketCap on 2026-07-26 showed it roughly agreeing with "
            "CoinGecko (~3.67M vs ~3.78M circulating supply, ~$189M vs ~$191M "
            "market cap) — not wired in as a live check, but a reassuring sanity "
            "check on the one number this app does rely on for Silver."
        )

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str] | None:
        # KAG is redeemable ~1:1 for a troy oz of silver, so the token quantity
        # already fetched doubles as the tokenized weight — no extra fetch.
        tokenized_oz = sum(c.quantity for c in result.components)
        total_oz = self._config.silver.total_tonnes * TROY_OZ_PER_TONNE
        return (format_tonnes(tokenized_oz), format_tonnes(total_oz))

    def _get_market_data(self) -> dict[str, MarketDataReading]:
        if self._market_cache is None:
            silver = self._config.silver
            coingecko_ids = [token.coingecko_id for token in silver.tokens]
            fallback_prices = {t.coingecko_id: t.fallback_price_usd for t in silver.tokens}
            fallback_supplies = {t.coingecko_id: t.fallback_supply for t in silver.tokens}
            self._market_cache = fetch_market_data(
                self._config.coingecko_base_url,
                coingecko_ids,
                fallback_prices,
                fallback_supplies,
                self._config.coingecko_timeout_seconds,
            )
        return self._market_cache
