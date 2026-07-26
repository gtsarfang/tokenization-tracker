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
    issuer: str
    # Plain-English description of the actual real-world collateral, not just what
    # the token trades for — this app is about what backs a token, not its price.
    backing: str
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
class TreasuryConfig:
    # Fallback only — the live total is fetched from the US Treasury's own API
    # (see sources/treasuries.py) since, unlike gold's above-ground stock, it
    # changes daily and a static constant would drift too fast to be meaningful.
    fallback_total_debt_usd: float
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
    treasuries: TreasuryConfig


# --- PAXG / XAUT contract facts (not user-tunable via env) ---------------------------

_PAXG = TokenConfig(
    symbol="PAXG",
    issuer="Paxos",
    backing=(
        "1 troy oz of a specific LBMA-certified 400oz gold bar, stored in Brink's "
        "vaults in London. Redeemable for physical gold delivery."
    ),
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
    issuer="Tether",
    backing=(
        "1 troy oz of individually serialized, allocated physical gold, stored in "
        "Swiss vaults. Redeemable for physical delivery in Switzerland."
    ),
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


# --- BUIDL / USDY contract facts (not user-tunable via env) ------------------------
# BUIDL and USDY are, as of 2026-07-26, two of the largest tokenized US Treasury
# products (BlackRock's BUIDL and Ondo's USDY). Circle's USYC is currently comparable
# in size or larger but isn't included yet — a candidate for a future addition, not
# because it's excluded on principle.

_BUIDL = TokenConfig(
    symbol="BUIDL",
    issuer="BlackRock",
    backing=(
        "Shares in a BlackRock money-market fund holding US Treasury bills, "
        "overnight repurchase agreements, and cash — assets custodied by BNY Mellon."
    ),
    contract_address="0x7712C34205737192402172409a8F7ccef8aA2AEc",
    expected_decimals=6,
    coingecko_id="blackrock-usd-institutional-digital-liquidity-fund",
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/blackrock-usd-institutional-digital-liquidity-fund
    fallback_supply=2_636_982_101.22,
    fallback_price_usd=1.00,
)

_USDY = TokenConfig(
    symbol="USDY",
    issuer="Ondo",
    backing=(
        "A note backed by short-term US Treasuries (held via Morgan Stanley) and "
        "bank deposits at insured US banks, in a bankruptcy-remote SPV. Accrues "
        "yield via a rising redemption value rather than a floating price."
    ),
    contract_address="0x96F6eF951840721AdBF46Ac996b59E0235CB985C",
    expected_decimals=18,
    coingecko_id="ondo-us-dollar-yield",
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/ondo-us-dollar-yield
    fallback_supply=1_894_599_428.93,
    fallback_price_usd=1.14,
)

_TREASURY_CONFIG = TreasuryConfig(
    # US Treasury Fiscal Data, "Debt Held by the Public" (Debt to the Penny),
    # 2026-07-23: $31.91T. Used only if the live API call fails — see
    # sources/treasuries.py for the live fetch.
    # https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/
    fallback_total_debt_usd=31_911_919_221_141.67,
    source_citation="US Treasury Fiscal Data API, 'Debt Held by the Public' (Debt to the Penny)",
    tokens=(_BUIDL, _USDY),
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
        treasuries=_TREASURY_CONFIG,
    )
