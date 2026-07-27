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
    # Narrower denominator: bars, coins, and gold-backed ETFs only — the actual
    # "investable" pool tokenized gold competes with, excluding jewelry,
    # central-bank reserves, and industrial stock (which `total_tonnes` includes).
    investment_tonnes: float = 0.0
    investment_source_citation: str = ""


@dataclass(frozen=True)
class SilverConfig:
    total_tonnes: float
    source_citation: str
    tokens: tuple[TokenConfig, ...]
    # Same narrower "investment stock" denominator as gold, using the Silver
    # Institute's "identifiable above-ground stocks" figure this app's own
    # `total_tonnes` deliberately did NOT use (see source_citation above).
    investment_tonnes: float = 0.0
    investment_source_citation: str = ""


@dataclass(frozen=True)
class TreasuryConfig:
    # Fallback only — the live total is fetched from the US Treasury's own API
    # (see sources/treasuries.py) since, unlike gold's above-ground stock, it
    # changes daily and a static constant would drift too fast to be meaningful.
    fallback_total_debt_usd: float
    source_citation: str
    tokens: tuple[TokenConfig, ...]


@dataclass(frozen=True)
class AppConfig:
    rpc_url: str
    rpc_timeout_seconds: float
    coingecko_base_url: str
    coingecko_timeout_seconds: float
    # Optional free CoinGecko Demo API key (RC_COINGECKO_API_KEY) for a higher
    # rate limit than the fully anonymous public tier. Not required — the app
    # works without one, just with a tighter rate limit.
    coingecko_api_key: str
    db_path: str
    gold: GoldConfig
    silver: SilverConfig
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
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/pax-gold if this drifts too far from live.
    fallback_supply=444_865.16,
    fallback_price_usd=4_086.05,
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
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/tether-gold if this drifts too far from live.
    fallback_supply=707_747.09,
    fallback_price_usd=4_081.53,
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
    fallback_price_usd=131.95,
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
    # World Gold Council, Gold Demand Trends Full Year 2024 — bars, coins, and
    # gold-backed ETFs, year-end 2024 estimate (48,634 tonnes). Retrieved
    # 2026-07-26. https://www.gold.org/goldhub/research/gold-demand-trends/gold-demand-trends-full-year-2024
    investment_tonnes=48_634.0,
    investment_source_citation=(
        "World Gold Council, Gold Demand Trends FY2024 — bars, coins & "
        "gold-backed ETFs (YE2024), retrieved 2026-07-26"
    ),
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
    fallback_price_usd=51.96,
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
    fallback_supply=438_043.99,
    fallback_price_usd=53.55,
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
    # Silver Institute, "identifiable above-ground stocks" (investment bars,
    # coins, and ETF holdings only) — ~79,000 tonnes, retrieved 2026-07-26.
    # This is the narrower figure `source_citation` above deliberately avoided
    # using as the primary denominator; used here as the alternate one instead.
    investment_tonnes=79_000.0,
    investment_source_citation=(
        "Silver Institute, 'identifiable above-ground stocks' (investment "
        "bars/coins/ETFs only), retrieved 2026-07-26"
    ),
)


# --- BUIDL / USDY / USYC contract facts (not user-tunable via env) ----------------
# BlackRock's BUIDL and Ondo's USDY were the two largest tokenized US Treasury
# products; Circle's USYC (Hashnote's US Yield Coin) is now comparable in size
# and included alongside them — see _TREASURY_CONFIG below for sizing.

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

_USYC = TokenConfig(
    symbol="USYC",
    issuer="Circle",
    backing=(
        "Shares in Hashnote's International Short Duration Yield Fund, holding "
        "short-term US Treasury bills and overnight reverse repurchase "
        "agreements collateralized by Treasuries."
    ),
    contract_address="0x136471a34f6ef19fE571EFFC1CA711fdb8E49f2b",
    expected_decimals=6,
    coingecko_id="hashnote-usyc",
    # Manual fallback, last observed 2026-07-26. Refresh periodically from
    # https://www.coingecko.com/en/coins/hashnote-usyc
    fallback_supply=2_655_466_907.77,
    fallback_price_usd=1.13,
    defillama_slug="circle-usyc",
    # Natively minted independently across Ethereum, Sui, and Canton Network —
    # same no-single-canonical-chain issue as BUIDL/USDY, so this uses
    # CoinGecko's aggregate total_supply rather than an on-chain read.
    read_onchain=False,
)

_JTRSY = TokenConfig(
    symbol="JTRSY",
    issuer="Janus Henderson",
    backing=(
        "Shares in the Janus Henderson Anemoy Treasury Fund, managed by Anemoy "
        "Capital and issued via the Centrifuge protocol, holding short-term US "
        "Treasury bills."
    ),
    contract_address="0x8c213EE79581Ff4984583C6a801e5263418C4b86",
    expected_decimals=6,
    coingecko_id="janus-henderson-anemoy-treasury-fund",
    # Manual fallback, last observed 2026-07-27. Refresh periodically from
    # https://www.coingecko.com/en/coins/janus-henderson-anemoy-treasury-fund
    fallback_supply=783_691_014.92,
    fallback_price_usd=1.11,
    # No dedicated slug — DefiLlama's "centrifuge-protocol" bundles multiple
    # Centrifuge-issued funds beyond just JTRSY, not a clean match.
    defillama_slug="",
    # Natively minted independently across Ethereum, Base, Plume, Monad, and
    # Avalanche — same no-single-canonical-chain issue as the other tokens here.
    read_onchain=False,
)

_USTB = TokenConfig(
    symbol="USTB",
    issuer="Superstate",
    backing=(
        "Shares in Superstate's Short Duration US Government Securities Fund "
        "(distributed in partnership with Invesco), holding short-term US "
        "Treasury and agency securities."
    ),
    contract_address="0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e",
    expected_decimals=6,
    coingecko_id="superstate-short-duration-us-government-securities-fund-ustb",
    # Manual fallback, last observed 2026-07-27. Refresh periodically from
    # https://www.coingecko.com/en/coins/invesco-short-duration-us-government-securities-fund
    fallback_supply=73_558_941.61,
    fallback_price_usd=11.16,
    defillama_slug="",
    # Natively minted independently across Ethereum, Plume, and Solana — same
    # no-single-canonical-chain issue as the other tokens here.
    read_onchain=False,
)

_OUSG = TokenConfig(
    symbol="OUSG",
    issuer="Ondo",
    backing=(
        "Shares in Ondo's short-term US Treasury bill fund, whose portfolio is "
        "held primarily via the iShares Short Treasury Bond ETF (SHV)."
    ),
    contract_address="0x1B19C19393e2d034D8Ff31ff34c81252fcBbee92",
    expected_decimals=18,
    coingecko_id="ousg",
    # Manual fallback, last observed 2026-07-27. Refresh periodically from
    # https://www.coingecko.com/en/coins/ousg
    # Note: CoinGecko's own market cap ($409M) runs ~15% below rwa.xyz's ($481M)
    # for this one — bigger gap than the other tokens here, but still the same
    # multi-chain-aggregate situation, not a sign of a wrong source.
    fallback_supply=3_525_544.62,
    fallback_price_usd=116.00,
    # No dedicated slug — "ondo-yield-assets" tracks USDY, not OUSG, and using
    # it here would double-count against the USDY row above.
    defillama_slug="",
    # Natively minted independently across Ethereum, Solana, and Polygon — same
    # no-single-canonical-chain issue as the other tokens here.
    read_onchain=False,
)

_WTGXX = TokenConfig(
    symbol="WTGXX",
    issuer="WisdomTree",
    backing=(
        "Shares in WisdomTree's regulated money market fund investing in "
        "short-term US government securities."
    ),
    contract_address="0x1FECf3D9d4FEe7f2c02917A66028A48c6706C179",
    expected_decimals=18,
    coingecko_id="wisdomtree-treasury-money-market-digital-fund",
    # Manual fallback, last observed 2026-07-27. Refresh periodically from
    # https://www.coingecko.com/en/coins/wisdomtree-treasury-money-market-digital-fund
    fallback_supply=736_592_592.0,
    fallback_price_usd=1.00,
    defillama_slug="",
    # Natively minted independently across Ethereum, Arbitrum, Base, Plume, and
    # Stellar — same no-single-canonical-chain issue as the other tokens here.
    read_onchain=False,
)

_TREASURY_CONFIG = TreasuryConfig(
    # US Treasury Fiscal Data, "Debt Held by the Public" (Debt to the Penny),
    # 2026-07-23: $31.91T (latest available as of 2026-07-26). Used only if the
    # live API call fails — see sources/treasuries.py for the live fetch.
    # https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/
    fallback_total_debt_usd=31_911_919_221_141.67,
    source_citation="US Treasury Fiscal Data API, 'Debt Held by the Public' (Debt to the Penny)",
    # BlackRock's BUIDL and Ondo's USDY were the two largest tokenized US
    # Treasury products; Circle's USYC (Hashnote's US Yield Coin, ~$3.0B AUM as
    # of 2026-07-26, per CoinGecko and DefiLlama agreeing closely) is now
    # comparable in size to BUIDL and is added alongside them. A 2026-07-27
    # coverage review (cross-checked against rwa.xyz's full ranked list, which
    # corrected several wrong estimates from an earlier, blog-sourced pass)
    # added WisdomTree's WTGXX (~$737M), Janus Henderson's JTRSY (~$870M, issued
    # via Centrifuge), Superstate's USTB (~$820M, distributed with Invesco), and
    # Ondo's OUSG (~$409M) — each independently >5% of the running total (OUSG
    # borderline; see its comment above). Franklin Templeton's BENJI/iBENJI and
    # JPMorgan's JLTXX (Kinexys) are bigger gaps still (~$2.5B and ~$811M) but
    # have no trustworthy live-fetchable source: CoinGecko's BENJI listing
    # undercounts by ~10x and JLTXX has no supply/price data at all (both are
    # permissioned/private-ledger products, not really tracked). ChinaAMC's
    # CUMIU (~$550M) isn't on CoinGecko or DefiLlama at all.
    tokens=(_BUIDL, _USDY, _USYC, _JTRSY, _USTB, _OUSG, _WTGXX),
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
        coingecko_api_key=os.environ.get("RC_COINGECKO_API_KEY", ""),
        db_path=os.environ.get("RC_DB_PATH", "data/reality_check.db"),
        gold=_GOLD_CONFIG,
        silver=_SILVER_CONFIG,
        treasuries=_TREASURY_CONFIG,
    )
