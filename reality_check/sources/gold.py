"""Gold asset-class source: PAXG + XAUT + KAU tokenized supply vs. total
above-ground gold value. Reference implementation of AssetClassSource for
future asset classes.

Takes a pre-fetched `market_data` dict (see `app.py`) rather than calling
CoinGecko itself — every source shares one batched `/coins/markets` request
covering all tokens app-wide, instead of each source hitting CoinGecko
independently (which was enough separate calls to trigger rate limiting).
"""

from __future__ import annotations

from config import TROY_OZ_PER_TONNE, AppConfig, TokenConfig, format_tonnes
from reality_check.models import AssetClassResult, ComponentValue, DataQuality, TotalValue
from reality_check.sources.defillama import defillama_cross_check_note, fetch_protocol_tvl
from reality_check.sources.onchain import get_web3, read_erc20_total_supply
from reality_check.sources.prices import MarketDataReading, MarketSupply, consistency_note, cross_check_note

# PAXG is redeemable 1:1 for a troy ounce of LBMA-good-delivery gold, so its market
# price is used as a live proxy for spot gold price (avoids a separate metals API).
_GOLD_SPOT_PROXY_COINGECKO_ID = "pax-gold"


class GoldSource:
    asset_class: str = "gold"

    def __init__(self, config: AppConfig, market_data: dict[str, MarketDataReading]) -> None:
        self._config = config
        self._market_data = market_data

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        onchain_tokens = [t for t in self._config.gold.tokens if t.read_onchain]
        aggregate_tokens = [t for t in self._config.gold.tokens if not t.read_onchain]
        components = [
            *self._fetch_onchain_components(onchain_tokens),
            *self._fetch_aggregate_components(aggregate_tokens),
        ]
        return tuple(components)

    def _fetch_onchain_components(self, tokens: list[TokenConfig]) -> list[ComponentValue]:
        if not tokens:
            return []
        w3 = get_web3(self._config.rpc_url, self._config.rpc_timeout_seconds)

        components = []
        for token in tokens:
            supply = read_erc20_total_supply(
                w3,
                token.contract_address,
                token.expected_decimals,
                token.fallback_supply,
            )
            market = self._market_data[token.coingecko_id]
            value_usd = supply.quantity * market.price_usd
            if market.quality is DataQuality.FALLBACK:
                # market.total_supply here is our own fallback constant, not a
                # live CoinGecko figure — comparing against it would misreport
                # a match/mismatch as if it meant something.
                verification = market.note
            else:
                verification = cross_check_note(supply.quantity, MarketSupply(market.total_supply, ""))
            defillama_note = ""
            if token.defillama_slug:
                defillama_reading = fetch_protocol_tvl(
                    token.defillama_slug, self._config.coingecko_timeout_seconds
                )
                defillama_note = defillama_cross_check_note(value_usd, defillama_reading)
            components.append(
                ComponentValue(
                    symbol=token.symbol,
                    quantity=supply.quantity,
                    unit_price_usd=market.price_usd,
                    value_usd=value_usd,
                    supply_quality=supply.quality,
                    price_quality=market.quality,
                    note="; ".join(n for n in (supply.note, verification, defillama_note) if n),
                    display_name=f"{token.issuer} {token.symbol}",
                    backing=token.backing,
                )
            )
        return components

    def _fetch_aggregate_components(self, tokens: list[TokenConfig]) -> list[ComponentValue]:
        # For tokens where the Ethereum contract doesn't hold the full supply
        # (e.g. natively minted on another ledger) — same CoinGecko-aggregate
        # pattern as silver.py/treasuries.py, not an on-chain read.
        components = []
        for token in tokens:
            reading = self._market_data[token.coingecko_id]
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
        return components

    def fetch_total(self) -> TotalValue:
        gold = self._config.gold
        spot = self._market_data[_GOLD_SPOT_PROXY_COINGECKO_ID]
        total_usd = gold.total_tonnes * TROY_OZ_PER_TONNE * spot.price_usd
        basis_note = (
            f"{gold.total_tonnes:,.0f} t ({gold.source_citation}) "
            f"@ ${spot.price_usd:,.2f}/oz (PAXG proxy, {spot.quality.value})"
        )
        return TotalValue(value_usd=total_usd, basis_note=basis_note, quality=spot.quality)

    def fetch_alt_total(self) -> TotalValue | None:
        gold = self._config.gold
        if not gold.investment_tonnes:
            return None
        spot = self._market_data[_GOLD_SPOT_PROXY_COINGECKO_ID]
        total_usd = gold.investment_tonnes * TROY_OZ_PER_TONNE * spot.price_usd
        basis_note = (
            f"{gold.investment_tonnes:,.0f} t bars/coins/ETFs only "
            f"({gold.investment_source_citation}) @ ${spot.price_usd:,.2f}/oz"
        )
        return TotalValue(value_usd=total_usd, basis_note=basis_note, quality=spot.quality)

    def describe_methodology(self) -> str:
        gold = self._config.gold
        onchain_symbols = " + ".join(t.symbol for t in gold.tokens if t.read_onchain)
        aggregate_symbols = " + ".join(t.symbol for t in gold.tokens if not t.read_onchain)
        symbols = " + ".join(token.symbol for token in gold.tokens)
        return (
            f"**Tokenized supply** — `totalSupply()` read directly from the "
            f"{onchain_symbols} ERC-20 contracts on their canonical Ethereum "
            f"mainnet addresses, via web3.py. {aggregate_symbols} is different: "
            "it's natively minted on Kinesis's own ledger (a Stellar fork), and "
            "an on-chain read of its Ethereum contract only captures a "
            "'wrapped' fraction of the real supply (~1.64M of ~2.39M tokens, "
            "verified 2026-07-26) — same underlying issue as Silver's KAG, so "
            f"{aggregate_symbols} uses CoinGecko's aggregate `total_supply` "
            "instead, like Silver and Treasuries do.\n\n"
            f"**Why {symbols}?** PAXG and XAUT are the two largest gold-backed "
            f"tokens by a wide margin. {aggregate_symbols} (Kinesis Gold, ~$315M) "
            "is a clear, worthwhile third (~6% on top of PAXG+XAUT combined) — "
            "the same 'worth it if not tiny' bar Silver's SLVON was added under. "
            "Smaller gold-backed tokens (e.g. Comtech Gold) are still excluded — "
            "this means the true tokenized total is a small undercount, never an "
            "overcount.\n\n"
            "**Is summing them correct — any overlap?** No double-counting: PAXG "
            "(Paxos), XAUT (Tether Gold), and KAU (Kinesis) are backed by "
            "separate, independently audited gold reserves, not shared "
            "collateral. For PAXG/XAUT specifically, we only read each token's "
            "canonical mainnet contract; if either is bridged/wrapped onto "
            "another chain, that's done by locking the mainnet tokens (which stay "
            "counted in mainnet `totalSupply`) and minting a claim elsewhere — not "
            "additional gold — so bridging doesn't cause double-counting either.\n\n"
            "**Prices** — fetched live from CoinGecko's `/coins/markets` endpoint, "
            "one shared request covering every token across every asset class "
            "in this app (see `app.py`), not a separate call per source.\n\n"
            "**Gold spot price** — derived from PAXG's market price rather than a "
            "separate metals API, since PAXG is redeemable 1:1 for a troy ounce of "
            "LBMA-good-delivery gold.\n\n"
            f"**Total gold value** = total above-ground tonnes × "
            f"{TROY_OZ_PER_TONNE:,.4f} troy oz/tonne × spot price, where total "
            f"tonnes ({gold.total_tonnes:,.0f} t) is from: {gold.source_citation}.\n\n"
            "**Alternate denominator (shown as a secondary figure)** — the "
            "primary total above includes jewelry, central-bank reserves, and "
            "industrial stock, none of which tokenized gold is realistically "
            "competing with. A narrower comparison uses only bars, coins, and "
            f"gold-backed ETFs ({gold.investment_tonnes:,.0f} t, "
            f"{gold.investment_source_citation}) — the actual investable pool.\n\n"
            "Any value that falls back to a manually configured constant (RPC or "
            "price API failure) is marked stale — see the badge above if so.\n\n"
            f"**Verification** — {onchain_symbols} are each cross-checked "
            "against two independent sources: CoinGecko's reported "
            "`total_supply`, and DefiLlama's tracked TVL for the same protocol "
            "(a genuinely separate data provider, not just a second CoinGecko "
            "call). Both are free, no-key APIs. Neither is a *better* source "
            "than the on-chain read itself, but agreement across three "
            "independent sources (chain, CoinGecko, DefiLlama) is a much "
            f"stronger signal than any one alone. {aggregate_symbols} only gets "
            "a same-source consistency check (like Silver/Private Credit), "
            "since CoinGecko's aggregate *is* its primary source and no free "
            "DefiLlama entry tracks Kinesis Money correctly."
        )

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str, str | None] | None:
        # PAXG, XAUT, and KAU are all redeemable ~1:1 for a troy oz of gold, so
        # the token quantities already fetched double as the tokenized weight —
        # no extra fetch.
        tokenized_oz = sum(c.quantity for c in result.components)
        total_oz = self._config.gold.total_tonnes * TROY_OZ_PER_TONNE
        gold = self._config.gold
        alt_qty = format_tonnes(gold.investment_tonnes * TROY_OZ_PER_TONNE) if gold.investment_tonnes else None
        return (format_tonnes(tokenized_oz), format_tonnes(total_oz), alt_qty)
