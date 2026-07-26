# Tokenization Tracker

How much of a real-world asset class has moved on-chain so far? This app tracks
tokenization's growth, one asset class at a time, as a fill-bar/gauge: full bar = the
asset class's total real-world value, filled portion = its tokenized value on-chain.

**v1 covers gold**: PAXG + XAUT tokenized supply vs. total above-ground gold value.
Tokenization is still early here — about 0.02% of total gold value is on-chain
today — so the bar pins the percentage label outside the fill with a leader line,
rather than centering unreadable text inside a few-pixel-wide sliver.

## Data sources & assumptions

**Tokenized gold supply** — read live from Ethereum via `web3.py`:
- [PAXG](https://etherscan.io/token/0x45804880de22913dafe09f4980848ece6ecbaf78) (Paxos
  Gold), contract `0x45804880De22913dAFE09f4980848ECE6EcbAf78`, 18 decimals
- [XAUT](https://etherscan.io/token/0x68749665ff8d2d112fa859aa293f07a622782f38) (Tether
  Gold), contract `0x68749665FF8D2d112Fa859AA293F07A622782F38`, 6 decimals

`totalSupply()` and `decimals()` are called directly on each contract via a free
public RPC (`https://ethereum.publicnode.com` by default).

**Token prices** — fetched from the [CoinGecko free API](https://www.coingecko.com/en/api)
`/simple/price` endpoint (no API key required), using CoinGecko ids `pax-gold` and
`tether-gold`.

**Gold spot price** — derived from PAXG's CoinGecko market price, not a separate
metals-price API. PAXG is redeemable 1:1 for a troy ounce of LBMA-good-delivery gold,
so its market price is a reasonable live proxy for spot gold, and reuses the price
call already needed for tokenized value.

**Total above-ground gold value** — `total_tonnes × troy_oz_per_tonne × spot_price`,
where `total_tonnes` is a static constant in `config.py`:

> World Gold Council, Goldhub "How Much Gold" dataset — above-ground stock, year-end
> 2024 estimate (216,265 tonnes). Retrieved 2026-07-25.
> https://www.gold.org/goldhub/data/how-much-gold

This figure changes slowly, so it's a periodically-updated constant rather than
something scraped live. Update it in `config.py` (with a fresh citation/date) as new
Goldhub estimates are published.

## Fallback / staleness handling

Both the on-chain supply reads and the CoinGecko price fetch can fail (RPC down, API
rate-limited). Each has a manually-configured fallback value in `config.py`
(`fallback_supply`, `fallback_price_usd` per token), seeded with a recently-observed
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

Click "Refresh" (per-asset) or "Refresh all" to re-fetch from RPC/CoinGecko and store
a new snapshot in SQLite (`data/reality_check.db`). History is preserved across runs,
enabling future charting of % tokenized over time.

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
├── viz.py             # Streamlit fill-bar rendering
└── sources/
    ├── onchain.py     # shared web3 ERC-20 supply reader
    ├── prices.py      # shared CoinGecko price fetcher
    └── gold.py        # GoldSource — reference AssetClassSource implementation
```

To add Treasuries (e.g. BUIDL/USDY vs. total UST market) or real estate (tokenized
property vs. total US real estate value):

1. Add a new module in `reality_check/sources/`, e.g. `treasuries.py`, implementing
   the `AssetClassSource` Protocol (`asset_class`, `fetch_tokenized()`,
   `fetch_total()`) — see `gold.py` for the reference pattern.
2. Add its config (contract addresses / API endpoints / fallback values / static
   totals with citations) to `config.py`.
3. Register it in `reality_check/registry.py`:
   `{"gold": GoldSource(config), "treasuries": TreasuriesSource(config)}`

No changes needed to `calc.py`, `storage.py`, or `viz.py` — they only depend on the
`AssetClassResult`/`ComponentValue`/`TotalValue` models, not on how a source produces
them.
