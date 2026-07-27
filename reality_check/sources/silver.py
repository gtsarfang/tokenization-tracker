"""Silver asset-class source: KAG + SLVON tokenized supply vs. total above-ground
silver value.

Neither is read on-chain directly. KAG is natively minted on Kinesis's own ledger
(a Stellar fork); its Ethereum ERC-20 contract is only a secondary "wrapped"
representation holding a small fraction of total supply. SLVON (Ondo's tokenized
iShares Silver Trust) is natively minted across Ethereum, BNB Chain, Solana, and
HyperEVM. Both use the same CoinGecko-aggregate-as-primary-source pattern as
`treasuries.py`, not a direct on-chain read like gold.py.
"""

from __future__ import annotations

from config import TROY_OZ_PER_TONNE, AppConfig, format_tonnes
from reality_check.models import AssetClassResult, ComponentValue, TotalValue
from reality_check.sources.prices import MarketDataReading, consistency_note


class SilverSource:
    asset_class: str = "silver"

    def __init__(self, config: AppConfig, market_data: dict[str, MarketDataReading]) -> None:
        self._config = config
        self._market_data = market_data

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        market = self._market_data

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
        # KAG specifically (not SLVON) is used as the spot-price proxy — it's a
        # direct 1:1 allocated-silver redemption, closer to spot than an ETF
        # share's NAV, which can drift slightly from spot over time (expense
        # ratio drag).
        spot_token = silver.tokens[0]
        spot = self._market_data[spot_token.coingecko_id]
        total_usd = silver.total_tonnes * TROY_OZ_PER_TONNE * spot.price_usd
        basis_note = (
            f"{silver.total_tonnes:,.0f} t ({silver.source_citation}) "
            f"@ ${spot.price_usd:,.2f}/oz ({spot_token.symbol} proxy, {spot.quality.value})"
        )
        return TotalValue(value_usd=total_usd, basis_note=basis_note, quality=spot.quality)

    def fetch_alt_total(self) -> TotalValue | None:
        silver = self._config.silver
        if not silver.investment_tonnes:
            return None
        spot_token = silver.tokens[0]
        spot = self._market_data[spot_token.coingecko_id]
        total_usd = silver.investment_tonnes * TROY_OZ_PER_TONNE * spot.price_usd
        basis_note = (
            f"{silver.investment_tonnes:,.0f} t investment bars/coins only "
            f"({silver.investment_source_citation}) @ ${spot.price_usd:,.2f}/oz"
        )
        return TotalValue(value_usd=total_usd, basis_note=basis_note, quality=spot.quality)

    def describe_methodology(self) -> str:
        silver = self._config.silver
        symbols = " + ".join(token.symbol for token in silver.tokens)
        spot_token = silver.tokens[0]
        return (
            f"**Tokenized supply & price** — fetched live from CoinGecko's "
            "`/coins/markets` endpoint (`total_supply × current_price`), part of "
            "one shared request covering every token across every asset class "
            f"in this app, *not* read on-chain directly. {spot_token.symbol} is natively minted on "
            "Kinesis's own ledger (a Stellar fork); its Ethereum ERC-20 contract "
            "is only a secondary 'wrapped' representation holding a small "
            "fraction of total supply. SLVON (Ondo's tokenized iShares Silver "
            "Trust) is natively minted across 4 chains (Ethereum, BNB Chain, "
            "Solana, HyperEVM). Both have the same underlying issue as "
            "Treasuries' BUIDL/USDY, so the same fix applies: use the "
            "aggregator's total instead of a single-chain on-chain read.\n\n"
            f"**Why {symbols}?** Kinesis Silver (KAG) is the largest tokenized "
            "silver product by a wide margin (~$194M). SLVON is the clear "
            "second (~$23M, ~12% on top of KAG) — worth including. A third "
            "(STRATO Silver, ~$3.5M, ~1.8% on top) isn't, at least not yet. "
            "This means the true tokenized total is an undercount, never an "
            "overcount.\n\n"
            "**Is summing them correct — any overlap?** No double-counting: KAG "
            "(direct allocated-silver redemption via Kinesis) and SLVON (shares "
            "of the iShares Silver Trust ETF, via Ondo) are backed by separate "
            "silver holdings, not a shared pool.\n\n"
            f"**Silver spot price** — derived from {spot_token.symbol}'s market "
            "price rather than a separate metals API, since it's redeemable 1:1 "
            "for a troy ounce of allocated silver.\n\n"
            "**Total silver value** — this is far murkier than gold's. The Silver "
            "Institute's 'identifiable above-ground stocks' (investment bars/coins "
            "only) is about 20x smaller than broader estimates that include "
            "jewelry, silverware, and industrial stock. To stay comparable with "
            "gold's WGC figure (which *does* include jewelry and industrial "
            f"holdings), this uses the broader estimate: {silver.source_citation}, "
            f"{silver.total_tonnes:,.0f} t total.\n\n"
            "**Alternate denominator (shown as a secondary figure)** — the "
            "narrower figure this app avoided using as primary is shown as a "
            f"comparison instead: {silver.investment_tonnes:,.0f} t of "
            f"identifiable investment stock ({silver.investment_source_citation}) "
            "— the pool tokenized silver is actually competing with.\n\n"
            "Any value that falls back to a manually configured constant "
            "(CoinGecko failure) is marked stale — see the badge above if so.\n\n"
            "**Verification** — like Treasuries, there's no independent on-chain "
            "figure to cross-check against (CoinGecko's aggregate *is* the primary "
            "source). Instead, `total_supply × price` is checked against "
            "CoinGecko's own reported `market_cap` from the same API response — "
            "this can't catch a wrong source, only an internally inconsistent one. "
            "DefiLlama has no entry that clearly tracks Kinesis Money (its "
            "'Kinesis Labs' listing is an unrelated protocol) or SLVON as of "
            "2026-07-26, so neither gets that extra check. A manual spot-check "
            "against CoinMarketCap on 2026-07-26 showed KAG roughly agreeing "
            "with CoinGecko (~3.67M vs ~3.78M circulating supply, ~$189M vs "
            "~$191M market cap) — not wired in as a live check, but reassuring."
        )

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str] | None:
        # Both KAG (direct redemption) and SLVON (an ETF share designed to track
        # ~1 oz of silver each) are close enough to 1:1 with a troy oz that the
        # token quantities already fetched double as tokenized weight — no extra
        # fetch. Same approximation level as gold's PAXG/XAUT already use.
        tokenized_oz = sum(c.quantity for c in result.components)
        total_oz = self._config.silver.total_tonnes * TROY_OZ_PER_TONNE
        return (format_tonnes(tokenized_oz), format_tonnes(total_oz))
