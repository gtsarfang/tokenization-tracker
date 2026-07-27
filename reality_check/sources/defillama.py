"""Free, no-key DefiLlama API — a genuinely independent second source of truth,
distinct from CoinGecko, for tokens it tracks under a directly comparable metric.

For a fully-backed RWA token (e.g. PAXG, BUIDL), DefiLlama's "TVL" figure for that
token's protocol equals the token's total value — not a narrower DeFi-collateral
usage metric — which is what makes it comparable to our own tokenized_usd figure.
Not every token has a DefiLlama entry tracking the right thing (verified manually
per-token before wiring in; see config.py's `defillama_slug` field), so this is
opt-in per token, not assumed to work generically.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

_BASE_URL = "https://api.llama.fi"


@dataclass(frozen=True)
class DefiLlamaReading:
    value_usd: float | None
    note: str


def fetch_protocol_tvl(slug: str, timeout_seconds: float) -> DefiLlamaReading:
    try:
        response = requests.get(f"{_BASE_URL}/tvl/{slug}", timeout=timeout_seconds)
        response.raise_for_status()
        return DefiLlamaReading(value_usd=float(response.text), note="")
    except (requests.RequestException, ValueError) as exc:
        return DefiLlamaReading(
            value_usd=None,
            note=f"DefiLlama cross-check unavailable ({exc.__class__.__name__})",
        )


def defillama_cross_check_note(
    our_value_usd: float, reading: DefiLlamaReading, tolerance: float = 0.10
) -> str:
    """Compares our tokenized value against DefiLlama's independently tracked TVL
    for the same entity. A mismatch flags something worth a look — it isn't
    automatically proof our number is wrong, since aggregators can differ in
    chain coverage or update timing, but it's a real second opinion, not a
    same-source consistency check."""
    if reading.value_usd is None:
        return reading.note
    if our_value_usd <= 0:
        return "DefiLlama cross-check skipped (zero value)"
    diff = abs(our_value_usd - reading.value_usd) / our_value_usd
    if diff > tolerance:
        return f"⚠ DefiLlama independently reports ${reading.value_usd / 1e9:.2f}B (differs by {diff:.1%})"
    return f"✓ matches DefiLlama's independent tracking (${reading.value_usd / 1e9:.2f}B, within {diff:.1%})"
