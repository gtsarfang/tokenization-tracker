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


def format_tonnes(troy_oz: float) -> str:
    tonnes = troy_oz / TROY_OZ_PER_TONNE
    if tonnes >= 1:
        return f"{tonnes:,.1f} t"
    return f"{tonnes * 1000:,.1f} kg"


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
    # DefiLlama protocol slug for an independent (non-CoinGecko) cross-check, e.g.
    # "paxos-gold" — verified manually to track this exact entity under a directly
    # comparable metric (see sources/defillama.py). Empty if no good match exists.
    defillama_slug: str = ""
    # False for tokens where the Ethereum contract doesn't hold the full supply
    # (e.g. natively minted on another ledger, with Ethereum only a small
    # "wrapped" fraction) — verified manually per token, not assumed. Those use
    # CoinGecko's aggregate `total_supply` instead of an on-chain read.
    read_onchain: bool = True


@dataclass(frozen=True)
class GoldConfig:
    total_tonnes: float
    source_citation: str
    tokens: tuple[TokenConfig, ...]


@dataclass(frozen=True)
class SilverConfig:
    total_tonnes: float
    source_citation: str
    tokens: tuple[TokenConfig, ...]


@dataclass(frozen=True)
class PrivateCreditConfig:
    total_market_usd: float
    source_citation: str
    tokens: tuple[TokenConfig, ...]


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
    silver: SilverConfig
    private_credit: PrivateCreditConfig
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
    defillama_slug="paxos-gold",
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
    defillama_slug="tether-gold",
)

_KAU = TokenConfig(
    symbol="KAU",
    issuer="Kinesis",
    backing=(
        "1 troy oz of allocated gold (999.9 fine), stored in fully insured, "
        "LBMA-standard vaults across six continents. Redeemable for physical "
        "delivery or vault withdrawal."
    ),
    contract_address="0x14dAB79fD7B7B3F748d434812fD6a9AaC460EA52",
    expected_decimals=18,
    coingecko_id="kinesis-gold",
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/kinesis-gold if this drifts too far from live.
    fallback_supply=2_386_227.83,
    fallback_price_usd=131.99,
    # Same issue as Silver's KAG: natively minted on Kinesis's own ledger (a
    # Stellar fork). An on-chain read of the Ethereum contract gave ~1.64M
    # tokens vs. CoinGecko's aggregate ~2.39M (verified 2026-07-26) — Ethereum
    # alone is a "wrapped" fraction, not the full supply.
    read_onchain=False,
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
    # PAXG and XAUT are the two largest gold-backed tokens by a wide margin. KAU
    # (Kinesis Gold, ~$315M) is a clear, worthwhile third (~6% on top of
    # PAXG+XAUT combined) — the same "worth it if not tiny" bar Silver's SLVON
    # was added under.
    tokens=(_PAXG, _XAUT, _KAU),
)


# --- KAG / SLVON contract facts (not user-tunable via env) ------------------------
# Kinesis Silver (KAG) is the dominant tokenized silver product by a wide margin
# (~$194M per DefiLlama, 2026-07-26). SLVON (Ondo's tokenized iShares Silver
# Trust) is the clear second (~$23M, ~12% on top of KAG) — worth including. A
# third (STRATO Silver, ~$3.5M, ~1.8% on top) isn't, at least not yet.

_KAG = TokenConfig(
    symbol="KAG",
    issuer="Kinesis",
    backing=(
        "1 troy oz of allocated silver (999+ fine), stored in fully insured, "
        "LBMA-standard vaults across six continents. Redeemable for physical "
        "delivery or vault withdrawal."
    ),
    contract_address="0x56BA8B58B7d1f6D384a1c4dd553f39ebc8741B8e",
    expected_decimals=18,
    coingecko_id="kinesis-silver",
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/kinesis-silver if this drifts too far from live.
    fallback_supply=3_777_096.93,
    fallback_price_usd=50.85,
)

_SLVON = TokenConfig(
    symbol="SLVON",
    issuer="Ondo",
    backing=(
        "Shares in the iShares Silver Trust (SLV) ETF — a BlackRock-managed "
        "trust holding physical silver bullion — held with US custodians via "
        "Ondo Global Markets. Redeemable 1:1 for SLV exposure."
    ),
    contract_address="0xf3E4872e6A4Cf365888D93b6146a2bAa7348F1a4",
    expected_decimals=18,
    coingecko_id="ishares-silver-trust-ondo-tokenized-stock",
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/ishares-silver-trust-ondo-tokenized-stock
    fallback_supply=438_081.95,
    fallback_price_usd=53.74,
)

_SILVER_CONFIG = SilverConfig(
    # Total above-ground silver is far murkier than gold's: the Silver Institute's
    # "identifiable above-ground stocks" (investment bars/coins only) is ~79,000
    # tonnes, but excludes jewelry/silverware/industrial stock — ~20x smaller than
    # broader estimates. To stay comparable with gold's WGC figure (which *does*
    # include jewelry and industrial holdings), this uses the broader estimate:
    # CPM Group / USGS-derived total above-ground silver (mined minus losses),
    # ~1.7 million tonnes as of 2018 (most recent widely-cited comprehensive
    # estimate), retrieved 2026-07-26.
    # https://cpmgroup.com/how-much-silver-is-above-ground/
    total_tonnes=1_700_000.0,
    source_citation=(
        "CPM Group, comprehensive above-ground silver estimate (~2018 data), "
        "retrieved 2026-07-26 — chosen over the Silver Institute's narrower "
        "'identifiable above-ground stocks' figure (~20x smaller) for "
        "comparability with gold's comprehensive WGC total"
    ),
    tokens=(_KAG, _SLVON),
)


# --- FIGR_HELOC contract facts (not user-tunable via env) -------------------------
# Figure's tokenized HELOC portfolio (FIGR_HELOC) is the dominant tokenized private
# credit product by a wide margin (~75% of the category). It runs on Provenance, a
# non-EVM chain we don't otherwise integrate with — but it's already tracked on
# CoinGecko like any other coin, so no Provenance-specific integration is needed;
# this uses the same CoinGecko-aggregate-as-primary-source pattern as
# silver.py/treasuries.py, just for a different underlying reason (non-EVM chain
# rather than multi-chain issuance).

_FIGR_HELOC = TokenConfig(
    symbol="FIGR_HELOC",
    issuer="Figure",
    backing=(
        "The unpaid principal balance of a portfolio of home equity lines of "
        "credit (HELOCs) originated by Figure Technology Solutions, recorded and "
        "managed on the Provenance blockchain."
    ),
    contract_address="scope1qrm5d0wjzamyywvjuws6774ljmrqu8kh9x",  # Provenance asset scope, not an EVM address
    expected_decimals=3,
    coingecko_id="figure-heloc",
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/figure-heloc if this drifts too far from live.
    fallback_supply=20_491_723_089.21,
    fallback_price_usd=1.034,
)

_PRIVATE_CREDIT_CONFIG = PrivateCreditConfig(
    # Global Market Insights Inc. (GMI), Report GMI16251, published 2026-07 —
    # global private credit market size, 2025 estimate. Retrieved 2026-07-26.
    # https://www.gminsights.com/industry-analysis/private-credit-market
    total_market_usd=2_100_000_000_000.0,
    source_citation="Global Market Insights Inc., Report GMI16251 (2025 estimate), retrieved 2026-07-26",
    tokens=(_FIGR_HELOC,),
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
    defillama_slug="blackrock-buidl",
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
    # DefiLlama's "Ondo Yield Assets" protocol description ("liquid exposure to an
    # ETF of short-term US Treasuries," a single share class) matches USDY
    # specifically rather than a bundle of Ondo products — verified 2026-07-26.
    defillama_slug="ondo-yield-assets",
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
        silver=_SILVER_CONFIG,
        private_credit=_PRIVATE_CREDIT_CONFIG,
        treasuries=_TREASURY_CONFIG,
    )
