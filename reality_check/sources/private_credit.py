"""Private credit asset-class source: FIGR_HELOC tokenized supply vs. total global
private credit market. Figure's tokenized HELOC portfolio (FIGR_HELOC) is the
dominant tokenized private credit product by a wide margin, unlike gold's
PAXG+XAUT pair — so there's just one component here.

FIGR_HELOC runs on Provenance, a non-EVM chain this app doesn't otherwise
integrate with. Rather than building a Provenance-specific client, this uses the
same CoinGecko-aggregate-as-primary-source pattern as `treasuries.py`/`silver.py`
— CoinGecko already tracks it like any other coin, so no new infrastructure is
needed.
"""

from __future__ import annotations

from config import AppConfig
from reality_check.models import AssetClassResult, ComponentValue, DataQuality, TotalValue
from reality_check.sources.prices import MarketDataReading, consistency_note


class PrivateCreditSource:
    asset_class: str = "private_credit"

    def __init__(self, config: AppConfig, market_data: dict[str, MarketDataReading]) -> None:
        self._config = config
        self._market_data = market_data

    def fetch_tokenized(self) -> tuple[ComponentValue, ...]:
        market = self._market_data

        components = []
        for token in self._config.private_credit.tokens:
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
        private_credit = self._config.private_credit
        return TotalValue(
            value_usd=private_credit.total_market_usd,
            basis_note=(
                f"{private_credit.total_market_usd / 1e12:,.1f}T "
                f"({private_credit.source_citation})"
            ),
            quality=DataQuality.LIVE,
        )

    def describe_methodology(self) -> str:
        private_credit = self._config.private_credit
        token = private_credit.tokens[0]
        return (
            f"**Tokenized supply & price** — fetched live from CoinGecko's "
            "`/coins/markets` endpoint (`total_supply × current_price`), *not* "
            f"read from a chain directly. {token.symbol} runs on Provenance, a "
            "non-EVM chain this app doesn't otherwise integrate with — rather "
            "than building a Provenance-specific client, this reuses the same "
            "CoinGecko-aggregate approach already used for Treasuries and "
            "Silver, since CoinGecko already tracks it like any other coin.\n\n"
            f"**Why only {token.symbol}?** Figure's tokenized HELOC portfolio is "
            "the dominant tokenized private credit product by a wide margin "
            "(~75% of the category). Other platforms (Maple Finance, Centrifuge, "
            "Goldfinch) exist and are smaller but real — candidates for a future "
            "addition, not excluded on principle. This means the true tokenized "
            "total is an undercount, never an overcount.\n\n"
            f"**What backs {token.symbol}?** {token.backing}\n\n"
            "**Total private credit market** — a static periodically-updated "
            f"estimate ({private_credit.source_citation}), similar in kind to "
            "gold's WGC figure: it changes slowly enough that a live daily fetch "
            "isn't necessary, unlike Treasury debt.\n\n"
            "Any value that falls back to a manually configured constant "
            "(CoinGecko failure) is marked stale — see the badge above if so.\n\n"
            "**Verification** — like Treasuries and Silver, there's no "
            "independent on-chain figure to cross-check against (CoinGecko's "
            "aggregate *is* the primary source). Instead, `total_supply × price` "
            "is checked against CoinGecko's own reported `market_cap` from the "
            "same API response. DefiLlama (used as a genuine second source for "
            "gold and Treasuries) was checked but its Figure-related listings "
            "track different products (the exchange platform, a lending pool) — "
            "not the HELOC certificate token itself — so it isn't used here.\n\n"
            "**Cross-checked manually against two sources** — a spot-check "
            "against CoinMarketCap on 2026-07-26 showed a materially different "
            "figure for FIGR_HELOC (~14.56B supply / ~$15.05B market cap vs. "
            "CoinGecko's ~20.49B / ~$21.19B, a ~27% gap). A further check "
            "against rwa.xyz showed it closely matching CoinGecko instead "
            "(~20.50B supply / ~$20.50B market cap) — so CoinMarketCap looks "
            "like the outlier here, not CoinGecko. Neither check is wired into "
            "the app as a live source (no free API for either), so this is "
            "documented rather than automated."
        )

    def describe_quantity(self, result: AssetClassResult) -> tuple[str, str] | None:
        return None  # no natural physical unit for private credit
