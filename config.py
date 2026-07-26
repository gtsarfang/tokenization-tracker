"""Typed application configuration.

Plain Python (not YAML/TOML) on purpose: the project already commits to dataclasses
and type hints everywhere, so this module *is* the config schema with no separate
parse/validate layer. Environment variables (loaded from `.env` via python-dotenv)
override the handful of deployment-specific values; facts about specific contracts
(addresses/decimals/CoinGecko ids) are not env-overridable since they aren't
deployment concerns.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Troy ounces per metric tonne. Standard conversion constant.
TROY_OZ_PER_TONNE = 32_150.7466


@dataclass(frozen=True)
class TokenConfig:
    symbol: str
    contract_address: str
    expected_decimals: int
    coingecko_id: str
    fallback_supply: float
    fallback_price_usd: float


@dataclass(frozen=True)
class GoldConfig:
    total_tonnes: float
    source_citation: str
    tokens: tuple[TokenConfig, TokenConfig]


@dataclass(frozen=True)
class AppConfig:
    rpc_url: str
    rpc_timeout_seconds: float
    coingecko_base_url: str
    coingecko_timeout_seconds: float
    db_path: str
    gold: GoldConfig


# --- PAXG / XAUT contract facts (not user-tunable via env) ---------------------------

_PAXG = TokenConfig(
    symbol="PAXG",
    contract_address="0x45804880De22913dAFE09f4980848ECE6EcbAf78",
    expected_decimals=18,
    coingecko_id="pax-gold",
    # Manual fallback, last observed 2026-07-25. Refresh periodically from
    # https://www.coingecko.com/en/coins/pax-gold if this drifts too far from live.
    fallback_supply=249_000.0,
    fallback_price_usd=3_360.0,
)

_XAUT = TokenConfig(
    symbol="XAUT",
    contract_address="0x68749665FF8D2d112Fa859AA293F07A622782F38",
    expected_decimals=6,
    coingecko_id="tether-gold",
    # Manual fallback, last observed 2026-07-25. Refresh periodically from
    # https://www.coingecko.com/en/coins/tether-gold if this drifts too far from live.
    fallback_supply=246_000.0,
    fallback_price_usd=3_365.0,
)

_GOLD_CONFIG = GoldConfig(
    # World Gold Council, Goldhub "How Much Gold" dataset — above-ground stock,
    # year-end 2024 estimate. Retrieved 2026-07-25.
    # https://www.gold.org/goldhub/data/how-much-gold
    total_tonnes=216_265.0,
    source_citation=(
        "World Gold Council, Goldhub 'How Much Gold' (above-ground stock, YE2024), "
        "retrieved 2026-07-25"
    ),
    tokens=(_PAXG, _XAUT),
)


def load_config() -> AppConfig:
    return AppConfig(
        rpc_url=os.environ.get("RC_RPC_URL", "https://ethereum.publicnode.com"),
        rpc_timeout_seconds=float(os.environ.get("RC_RPC_TIMEOUT_SECONDS", "8.0")),
        coingecko_base_url=os.environ.get(
            "RC_COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3"
        ),
        coingecko_timeout_seconds=float(
            os.environ.get("RC_COINGECKO_TIMEOUT_SECONDS", "8.0")
        ),
        db_path=os.environ.get("RC_DB_PATH", "data/reality_check.db"),
        gold=_GOLD_CONFIG,
    )
