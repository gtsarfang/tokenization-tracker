"""Gold asset-class source: PAXG + XAUT tokenized supply vs. total above-ground
gold value. Reference implementation of AssetClassSource for future asset classes."""

from __future__ import annotations

from config import TROY_OZ_PER_TONNE, AppConfig
from reality_check.models import ComponentValue, TotalValue
from reality_check.sources.onchain import get_web3, read_erc20_total_supply
from reality_check.sources.prices import PriceReading, fetch_simple_prices

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

        components = []
        for token in self._config.gold.tokens:
            supply = read_erc20_total_supply(
                w3,
                token.contract_address,
                token.expected_decimals,
                token.fallback_supply,
            )
            price = prices[token.coingecko_id]
            components.append(
                ComponentValue(
                    symbol=token.symbol,
                    quantity=supply.quantity,
                    unit_price_usd=price.price_usd,
                    value_usd=supply.quantity * price.price_usd,
                    supply_quality=supply.quality,
                    price_quality=price.quality,
                    note="; ".join(n for n in (supply.note, price.note) if n),
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
