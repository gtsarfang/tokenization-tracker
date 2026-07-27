"""Gold asset-class source: PAXG + XAUT tokenized supply vs. total above-ground
gold value. Reference implementation of AssetClassSource for future asset classes."""

from __future__ import annotations

from config import TROY_OZ_PER_TONNE, AppConfig, format_tonnes
from reality_check.models import AssetClassResult, ComponentValue, TotalValue
from reality_check.sources.defillama import defillama_cross_check_note, fetch_protocol_tvl
from reality_check.sources.onchain import get_web3, read_erc20_total_supply
from reality_check.sources.prices import (
    PriceReading,
    cross_check_note,
    fetch_cross_check_supply,
    fetch_simple_prices,
)

# PAXG is redeemable 1:1 for a troy ounce of LBMA-good-delivery gold, so its market
# price is used as a live proxy for spot gold price (avoids a separate metals API).
_GOLD_SPOT_PROXY_COINGECKO_ID = "pax-gold"


class GoldSource:
    asset_class: str = "gold"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._price_cache: dict[str, PriceReading] | None = None

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        w3 = get_web3(self._config.rpc_url, self._config.rpc_timeout_seconds)
        prices = self._get_prices()
        cross_checks = fetch_cross_check_supply(
            self._config.coingecko_base_url,
            [token.coingecko_id for token in self._config.gold.tokens],
            self._config.coingecko_timeout_seconds,
        )

        components = []
        for token in self._config.gold.tokens:
            supply = read_erc20_total_supply(
                w3,
                token.contract_address,
                token.expected_decimals,
                token.fallback_supply,
            )
            price = prices[token.coingecko_id]
            value_usd = supply.quantity * price.price_usd
            verification = cross_check_note(supply.quantity, cross_checks[token.coingecko_id])
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
                    unit_price_usd=price.price_usd,
                    value_usd=value_usd,
                    supply_quality=supply.quality,
                    price_quality=price.quality,
                    note="; ".join(
                        n for n in (supply.note, price.note, verification, defillama_note) if n
                    ),
                    display_name=f"{token.issuer} {token.symbol}",
                    backing=token.backing,
                )
            )
        return tuple(components)

    def fetch_total(self) -> TotalValue:
        gold = self._config.gold
        spot = self._get_prices()[_GOLD_SPOT_PROXY_COINGECKO_ID]
        total_usd = gold.total_tonnes * TROY_OZ_PER_TONNE * spot.price_usd
        basis_note = (
            f"{gold.total_tonnes:,.0f} t ({gold.source_citation}) "
            f"@ ${spot.price_usd:,.2f}/oz (PAXG proxy, {spot.quality.value})"
        )
        return TotalValue(value_usd=total_usd, basis_note=basis_note, quality=spot.quality)

    def describe_methodology(self) -> str:
        gold = self._config.gold
        symbols = " + ".join(token.symbol for token in gold.tokens)
        return (
            f"**Tokenized supply** — `totalSupply()` read directly from the "
            f"{symbols} ERC-20 contracts on their canonical Ethereum mainnet "
            f"addresses, via web3.py.\n\n"
            f"**Why only {symbols}?** They're the two largest gold-backed tokens "
            "by market cap by a wide margin. Smaller gold-backed tokens exist "
            "(e.g. Kinesis KAU, Comtech Gold) but are excluded here as negligible "
            "in size — this means the true tokenized total is a small undercount, "
            "never an overcount.\n\n"
            "**Is summing them correct — any overlap?** No double-counting: PAXG "
            "(Paxos) and XAUT (Tether Gold) are backed by separate, independently "
            "audited gold reserves, not shared collateral. We only read each "
            "token's canonical mainnet contract; if either is bridged/wrapped onto "
            "another chain, that's done by locking the mainnet tokens (which stay "
            "counted in mainnet `totalSupply`) and minting a claim elsewhere — not "
            "additional gold — so bridging doesn't cause double-counting either.\n\n"
            "**Prices** — fetched live from the CoinGecko free API "
            "(`/simple/price`).\n\n"
            "**Gold spot price** — derived from PAXG's market price rather than a "
            "separate metals API, since PAXG is redeemable 1:1 for a troy ounce of "
            "LBMA-good-delivery gold.\n\n"
            f"**Total gold value** = total above-ground tonnes × "
            f"{TROY_OZ_PER_TONNE:,.4f} troy oz/tonne × spot price, where total "
            f"tonnes ({gold.total_tonnes:,.0f} t) is from: {gold.source_citation}.\n\n"
            "Any value that falls back to a manually configured constant (RPC or "
            "price API failure) is marked stale — see the badge above if so.\n\n"
            "**Verification** — each reading is cross-checked against two "
            "independent sources: CoinGecko's reported `total_supply`, and "
            "DefiLlama's tracked TVL for the same protocol (a genuinely separate "
            "data provider, not just a second CoinGecko call). Both are free, "
            "no-key APIs. Neither is a *better* source than the on-chain read "
            "itself, but agreement across three independent sources (chain, "
            "CoinGecko, DefiLlama) is a much stronger signal than any one alone."
        )

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str] | None:
        # PAXG and XAUT are both redeemable ~1:1 for a troy oz of gold, so the token
        # quantities already fetched double as the tokenized weight — no extra fetch.
        tokenized_oz = sum(c.quantity for c in result.components)
        total_oz = self._config.gold.total_tonnes * TROY_OZ_PER_TONNE
        return (format_tonnes(tokenized_oz), format_tonnes(total_oz))

    def _get_prices(self) -> dict[str, PriceReading]:
        if self._price_cache is None:
            coingecko_ids = [token.coingecko_id for token in self._config.gold.tokens]
            fallback_prices = {
                token.coingecko_id: token.fallback_price_usd
                for token in self._config.gold.tokens
            }
            self._price_cache = fetch_simple_prices(
                self._config.coingecko_base_url,
                coingecko_ids,
                fallback_prices,
                self._config.coingecko_timeout_seconds,
            )
        return self._price_cache
