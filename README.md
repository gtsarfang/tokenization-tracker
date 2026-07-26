# Tokenization Tracker

How much of a real-world asset class has moved on-chain so far? This app tracks
tokenization's growth, one asset class at a time: a big headline stat (%, $, or —
where it makes sense — physical units), plus a log-scale bar comparing tokenized
value against the asset class's total real-world value. A linear fill-bar can't show
a fraction this small (tokenized gold is ~0.02% of all gold) without the fill being
imperceptible, so the comparison is log-scale instead, with order-of-magnitude
gridlines so it reads as log rather than an arbitrary line.

Currently covers **gold** (PAXG + XAUT vs. total above-ground gold value),
**silver** (KAG vs. total above-ground silver value), and **Treasuries** (BUIDL +
USDY vs. total US Treasury debt held by the public). Cards render in a 3-per-row
grid (wide page layout) that keeps filling out as more asset classes are added.

![Screenshot](docs/screenshot.jpg)

## Data sources & assumptions

### Gold

**Tokenized supply** — read live from Ethereum via `web3.py`:
- [PAXG](https://etherscan.io/token/0x45804880de22913dafe09f4980848ece6ecbaf78) (Paxos
  Gold), contract `0x45804880De22913dAFE09f4980848ECE6EcbAf78`, 18 decimals
- [XAUT](https://etherscan.io/token/0x68749665ff8d2d112fa859aa293f07a622782f38) (Tether
  Gold), contract `0x68749665FF8D2d112Fa859AA293F07A622782F38`, 6 decimals

`totalSupply()` and `decimals()` are called directly on each contract via a free
public RPC (`https://ethereum.publicnode.com` by default).

PAXG and XAUT are the two largest gold-backed tokens by market cap by a wide
margin. Smaller ones exist (Kinesis KAU, Comtech Gold, etc.) but are excluded as
negligible — so the tokenized total here is a slight *undercount*, never an
overcount. Summing PAXG + XAUT doesn't double-count: they're backed by separate,
independently audited gold reserves, not shared collateral. Only each token's
canonical Ethereum mainnet contract is read — if either is bridged/wrapped onto
another chain, that's done by locking the mainnet tokens (which stay counted in
mainnet `totalSupply`) and minting a claim elsewhere, not additional gold, so
bridging doesn't introduce double-counting either.

**Token prices** — fetched from the [CoinGecko free API](https://www.coingecko.com/en/api)
`/simple/price` endpoint (no API key required), using CoinGecko ids `pax-gold` and
`tether-gold`.

**Gold spot price** — derived from PAXG's CoinGecko market price, not a separate
metals-price API. PAXG is redeemable 1:1 for a troy ounce of LBMA-good-delivery gold,
so its market price is a reasonable live proxy for spot gold, and reuses the price
call already needed for tokenized value. The same 1:1 relationship also means the
raw token quantities double as the tokenized *weight* — the "mass" display mode
sums PAXG + XAUT quantities directly, no extra fetch needed.

**Total above-ground gold value** — `total_tonnes × troy_oz_per_tonne × spot_price`,
where `total_tonnes` is a static constant in `config.py`:

> World Gold Council, Goldhub "How Much Gold" dataset — above-ground stock, year-end
> 2024 estimate (216,265 tonnes). Retrieved 2026-07-25.
> https://www.gold.org/goldhub/data/how-much-gold

This figure changes slowly, so it's a periodically-updated constant rather than
something scraped live. Update it in `config.py` (with a fresh citation/date) as new
Goldhub estimates are published.

### Silver

**Tokenized supply & price** — fetched live from CoinGecko's `/coins/markets`
endpoint (`total_supply × current_price`), *not* read from the
[KAG](https://www.coingecko.com/en/coins/kinesis-silver) (Kinesis Silver) Ethereum
contract (`0x56BA8B58B7d1f6D384a1c4dd553f39ebc8741B8e`). KAG is natively minted on
Kinesis's own ledger (a Stellar fork) — the Ethereum ERC-20 contract is only a
secondary "wrapped" representation holding a small fraction of total supply (an
on-chain read there gave ~35,000 tokens vs. CoinGecko's aggregate ~3.78M). Same
underlying issue as Treasuries' BUIDL/USDY, same fix: use the aggregator instead of
a single-chain read.

Kinesis Silver is the dominant tokenized silver product by a wide margin — no
second silver token is large enough yet to be worth including, unlike gold's
PAXG+XAUT pair, so again this is an undercount, never an overcount.

**Total above-ground silver value** — this denominator is far murkier than gold's.
The Silver Institute's "identifiable above-ground stocks" (investment bars/coins
only, ~79,000 tonnes) is about 20x smaller than broader estimates that include
jewelry, silverware, and industrial stock. To stay comparable with gold's WGC
figure (which *does* include jewelry and industrial holdings), this uses the
broader estimate:

> CPM Group, comprehensive above-ground silver estimate (~2018 data, ~1.7 million
> tonnes). Retrieved 2026-07-26.
> https://cpmgroup.com/how-much-silver-is-above-ground/

This citation choice matters a lot for the resulting percentage — a reader
comparing this app's silver number against one using the narrower Silver Institute
figure will see a ~20x difference for reasons that have nothing to do with data
quality.

### Treasuries

**Tokenized supply & price** — fetched live from CoinGecko's `/coins/markets`
endpoint (`total_supply × current_price`), *not* read from a single on-chain
contract like gold's PAXG/XAUT:
- [BUIDL](https://www.coingecko.com/en/coins/blackrock-usd-institutional-digital-liquidity-fund)
  (BlackRock USD Institutional Digital Liquidity Fund) — Ethereum contract
  `0x7712C34205737192402172409a8F7ccef8aA2AEc`, but also natively minted on Solana,
  Avalanche, Arbitrum, Optimism, Polygon, and Aptos
- [USDY](https://www.coingecko.com/en/coins/ondo-us-dollar-yield) (Ondo US Dollar
  Yield) — Ethereum contract `0x96F6eF951840721AdBF46Ac996b59E0235CB985C`, also
  natively minted on Solana, Arbitrum, Mantle, Sui, and others

**Why not read on-chain like gold does?** This was the original plan, and the first
implementation did exactly that — reading `totalSupply()` from each token's Ethereum
mainnet contract, same as PAXG/XAUT. The cross-check verification (below) caught
that this undercounted BUIDL by ~13x and USDY by ~2x. Unlike PAXG/XAUT, which are
single-canonical-chain tokens (Ethereum mainnet `totalSupply()` already reflects the
full circulating supply, with any bridged copies backed by locked mainnet tokens),
BUIDL and USDY are natively minted independently on each chain they're deployed to
— there's no single canonical chain whose supply represents the global total. So for
these two, CoinGecko's cross-chain-aggregated `total_supply` is used as the primary
source instead of a single-chain on-chain read.

BUIDL and USDY are two of the largest tokenized US Treasury products (as of
2026-07-26). Circle's USYC is currently comparable in size or larger but isn't
included yet — a candidate for a future addition, not excluded on principle, so
again this is an undercount, never an overcount. No double-counting: both are
independently managed funds holding their own short-term Treasury instruments, not
wrapped/derivative versions of each other.

**Total Treasury debt** — fetched **live** on every refresh from the US Treasury's
own [Fiscal Data API](https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/)
(`debt_to_penny`), using "Debt Held by the Public" (total public debt minus
intragovernmental holdings) as the closest live, daily-updated proxy for total
marketable Treasury debt. Unlike gold's above-ground stock, this changes daily, so
it's not a static config constant — only a fallback value is stored in `config.py`,
used solely if the live API call fails.

## Verification / cross-checking

For single-chain tokens like gold's PAXG/XAUT, on-chain `totalSupply()` is already
the ground truth — nothing outranks reading the contract itself. But it's still
possible to misconfigure a contract address or decimals value, so every such reading
is cross-checked against CoinGecko's independently reported `total_supply` for the
same token (`/coins/markets`). This is a sanity check for bugs, not a better source
of truth: if the two disagree by more than 2%, the mismatch is flagged; otherwise a
confirmation note is recorded. Results are shown under each asset's "How is this
calculated?" expander as "Latest verification".

This check is exactly what caught the Treasuries and Silver multi-chain/multi-ledger
issues described above — it's not just theoretical insurance, it changed the
implementation twice.

Treasuries and Silver don't get this same cross-check, since CoinGecko's aggregate
*is* their primary source — there's no better independent figure to check it
against. Instead, for those, `total_supply × price` is checked against CoinGecko's
own reported `market_cap` from the same API response, which can catch an internally
inconsistent response (e.g. a stale field) but not a wrong source.

## Fallback / staleness handling

On-chain supply reads, CoinGecko price/cross-check fetches, and (for Treasuries) the
Treasury Fiscal Data API call can all fail (RPC down, API rate-limited). Each has a
manually-configured fallback value in `config.py`, seeded with a recently-observed
value and a comment noting when it was last refreshed — refresh these occasionally so
they don't drift too far from reality.

Every computed value carries a `DataQuality.LIVE` or `DataQuality.FALLBACK` tag.
`AssetClassResult.is_stale()` is true if *any* underlying value fell back, and the
Streamlit UI shows a "stale (fallback data in use)" badge in that case — so the app
degrades gracefully instead of crashing, and it's always visible when a number isn't
live.

## Running locally

```bash
python -m venv .venv
./.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # optional — defaults work out of the box
streamlit run app.py
```

Click "Refresh" (per-asset) or "Refresh all" to re-fetch live data and store a new
snapshot in SQLite (`data/reality_check.db`). History is preserved across runs,
enabling future charting of % tokenized over time.

The Streamlit "Deploy" toolbar button is hidden by default (`.streamlit/config.toml`,
`toolbarMode = "minimal"`) since this app isn't meant to be one-click-deployed from a
local dev session — it doesn't affect the ability to actually deploy the app (e.g. via
Streamlit Community Cloud connected to this GitHub repo) when you're ready to.

## Running tests

```bash
pytest tests/
```

Tests cover the pure calculation logic (`reality_check/calc.py`) only — no network,
RPC, or database dependency.

## Architecture / adding a new asset class

```
reality_check/
├── models.py         # AssetClassResult, ComponentValue, TotalValue, DataQuality
├── calc.py            # pure pct_tokenized math — the only unit-tested surface
├── interfaces.py      # AssetClassSource contract
├── registry.py        # asset_class slug -> AssetClassSource instance
├── orchestrator.py     # source -> calc -> storage glue
├── storage.py         # SQLite schema + repository functions
├── viz.py             # Streamlit card/hero-stat/log-scale-bar rendering
└── sources/
    ├── onchain.py     # shared web3 ERC-20 supply reader
    ├── prices.py      # shared CoinGecko price fetcher + cross-check/consistency helpers
    ├── gold.py        # GoldSource — on-chain-read reference implementation
    ├── silver.py      # SilverSource — CoinGecko-aggregate reference implementation
    └── treasuries.py  # TreasurySource — live-total-fetch + CoinGecko-aggregate implementation
```

To add a new asset class (e.g. tokenized real estate):

1. Add a new module in `reality_check/sources/`, implementing the `AssetClassSource`
   Protocol (`asset_class`, `fetch_tokenized()`, `fetch_total()`,
   `describe_methodology()`, `describe_quantity()`) — see `gold.py` (static total) or
   `treasuries.py` (live-fetched total) for reference patterns.
2. Add its config (contract addresses / API endpoints / fallback values / static
   totals with citations) to `config.py`.
3. Register it in `reality_check/registry.py`.
4. Add a visual theme entry (accent color, icon, log-bar gradient) to `_ASSET_THEME`
   in `reality_check/viz.py` — asset classes without one fall back to a neutral gray
   theme automatically, so this step is optional but recommended.

No changes needed to `calc.py` or `storage.py` — they only depend on the
`AssetClassResult`/`ComponentValue`/`TotalValue` models, not on how a source produces
them.
