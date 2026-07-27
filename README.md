# Tokenization Tracker

How much of a real-world asset class has moved on-chain so far? This app tracks
tokenization's growth, one asset class at a time: a big headline stat (%, $, or —
where it makes sense — physical units), plus a log-scale bar comparing tokenized
value against the asset class's total real-world value. A linear fill-bar can't show
a fraction this small (tokenized gold is ~0.02% of all gold) without the fill being
imperceptible, so the comparison is log-scale instead, with order-of-magnitude
gridlines so it reads as log rather than an arbitrary line.

Currently covers **gold** (PAXG + XAUT vs. total above-ground gold value),
**silver** (KAG vs. total above-ground silver value), **Treasuries** (BUIDL + USDY
vs. total US Treasury debt held by the public), and **private credit**
(FIGR_HELOC vs. total global private credit market — currently ~1%, a much
further-along story than the other three, which sit around 0.01-0.02%). Cards
render in a 3-per-row grid (wide page layout) that keeps filling out as more
asset classes are added.

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

**Tokenized value** — BUIDL (BlackRock USD Institutional Digital Liquidity Fund)
and USDY (Ondo US Dollar Yield) are natively minted independently on multiple
chains (BUIDL on 8, USDY on 12), each with its own separate supply — there's no
single canonical chain whose `totalSupply()` represents the global total.

This went through two fixes, not one:
1. **First implementation**: read `totalSupply()` from each token's Ethereum
   mainnet contract, same as gold's PAXG/XAUT. The CoinGecko cross-check caught
   that this undercounted BUIDL by ~13x and USDY by ~2x, since — unlike
   PAXG/XAUT, which are single-canonical-chain tokens — these two have no chain
   whose local supply represents the total.
2. **Second fix**: switched to CoinGecko's `/coins/markets` `total_supply ×
   current_price` (its own claimed cross-chain aggregate). Checking that against
   [DefiLlama](https://defillama.com/rwa) — a free, no-key, independent
   aggregator with a public per-chain TVL breakdown — showed CoinGecko
   *also* undercounts both: by ~30% for BUIDL, ~19% for USDY (as of
   2026-07-26). DefiLlama's protocol pages
   ([blackrock-buidl](https://defillama.com/protocol/blackrock-buidl),
   [ondo-yield-assets](https://defillama.com/protocol/ondo-yield-assets)) sum
   TVL explicitly across every chain they track the protocol on, which turned
   out to be more complete than CoinGecko's supposedly-aggregated
   `total_supply` for these two tokens specifically.

DefiLlama's TVL is now used as the primary tokenized value when available, with
CoinGecko's `total_supply × price` kept as a fallback and shown alongside it for
comparison. (Gold's PAXG/XAUT don't have this problem — checked the same way,
their on-chain reads matched DefiLlama within 0.5%, confirming they really are
single-canonical-chain tokens.)

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

### Private credit

**Tokenized supply & price** — fetched live from CoinGecko's `/coins/markets`
endpoint (`total_supply × current_price`), same as Treasuries/Silver:
- [FIGR_HELOC](https://www.coingecko.com/en/coins/figure-heloc) (Figure) — the
  unpaid principal balance of a portfolio of home equity lines of credit (HELOCs)
  originated by Figure Technology Solutions

**Why CoinGecko instead of an on-chain read?** FIGR_HELOC runs on
[Provenance](https://provenance.io/), a non-EVM blockchain this app doesn't
otherwise integrate with (no `web3.py` support, different address format
entirely). Building a Provenance-specific client for one token wasn't worth it —
CoinGecko already tracks FIGR_HELOC like any other coin, so this reuses the exact
same aggregate-source pattern already built for Treasuries/Silver, just for a
different underlying reason (non-EVM chain rather than multi-chain issuance).

**Why only FIGR_HELOC?** Figure's tokenized HELOC portfolio is the dominant
tokenized private credit product by a wide margin (~75% of the category as of
early 2026). Other platforms (Maple Finance, Centrifuge, Goldfinch) are real but
smaller — candidates for a future addition, not excluded on principle. This means
the true tokenized total is an undercount, never an overcount.

**Total private credit market** — a periodically-updated estimate, similar in
kind to gold's WGC figure:

> Global Market Insights Inc., Report GMI16251, 2025 estimate ($2.1 trillion).
> Retrieved 2026-07-26.
> https://www.gminsights.com/industry-analysis/private-credit-market

This is why private credit shows ~1% tokenized while the other three cards sit
around 0.01-0.02% — it's a genuinely different, further-along category, not a
different methodology being applied inconsistently.

## Verification / cross-checking

Three tiers, depending on what's available for a given token:

1. **Independent second source** (Gold's PAXG/XAUT, Treasuries' BUIDL/USDY) — a
   genuinely separate data provider corroborates (or, as it turned out, corrects)
   the primary source. For gold, on-chain `totalSupply()` is cross-checked against
   both CoinGecko's `total_supply` and [DefiLlama](https://defillama.com/rwa)'s
   tracked TVL for the same protocol — free, no-key APIs, verified manually to
   track the right entity under a comparable metric before being wired in. For
   Treasuries, DefiLlama and CoinGecko effectively check each other, and
   DefiLlama's more-complete per-chain sum won out as primary (see above).
2. **Same-source consistency check** (Silver, Private Credit) — `total_supply ×
   price` is checked against CoinGecko's own reported `market_cap` from the same
   API response. This can catch an internally inconsistent response (e.g. a stale
   field) but not a wrong source, since there's no second provider tracking these
   specific tokens under a comparable metric. [rwa.xyz](https://rwa.xyz) was
   considered as a possible second source for these, but its API requires a paid/
   institutional subscription (a discount exists for students/early-stage
   projects, but it isn't free), which doesn't fit this app's "no signup, no key"
   pattern — DefiLlama was checked instead specifically because it's free.
3. **None available** — not every free provider tracks every token. DefiLlama's
   "Kinesis Labs" listing is an unrelated protocol (not Kinesis Money/KAG), and
   its Figure-related listings track different products (the exchange platform, a
   lending pool), not the FIGR_HELOC certificate token — so Silver and Private
   Credit fall back to tier 2 only. A one-off manual spot-check against
   CoinMarketCap on 2026-07-26 (not wired into the app — no API key configured)
   found Silver's number reassuringly close (~$189M vs. CoinGecko's ~$191M), but
   Private Credit's materially different (~$15.05B vs. CoinGecko's ~$21.19B, a
   ~27% gap) — documented as an open question in `private_credit.py`'s
   methodology text rather than silently resolved, since FIGR_HELOC's supply
   genuinely fluctuates (tracks unpaid loan principal) and there's no clear
   evidence which aggregator is more current.

Results are shown under each asset's "How is this calculated?" expander as "Latest
verification". This is exactly what caught the Treasuries and Silver
multi-chain/multi-ledger issues described above, and then caught a *second*,
smaller undercount in Treasuries after the first fix — it's not just theoretical
insurance, it changed the implementation three times across two asset classes.

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

Each asset class re-fetches live data automatically at most once every 5 minutes
(`st.cache_data(ttl=300)` in `app.py`) — no manual refresh button. This keeps the
page responsive to UI interactions (like toggling %/$/mass) without re-hitting
every API on each rerun, while still staying reasonably fresh. Each live fetch
stores a new snapshot in SQLite (`data/reality_check.db`); history is preserved
across runs, enabling future charting of % tokenized over time.

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
    ├── onchain.py         # shared web3 ERC-20 supply reader
    ├── prices.py          # shared CoinGecko price fetcher + cross-check/consistency helpers
    ├── defillama.py       # shared free/no-key DefiLlama TVL fetcher + cross-check helper
    ├── gold.py            # GoldSource — on-chain-read reference implementation
    ├── silver.py          # SilverSource — CoinGecko-aggregate reference implementation
    ├── treasuries.py      # TreasurySource — live-total-fetch + DefiLlama/CoinGecko implementation
    └── private_credit.py  # PrivateCreditSource — CoinGecko-aggregate for a non-EVM-chain token
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
