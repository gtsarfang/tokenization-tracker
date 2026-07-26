"""Card-based hero-stat + log-scale comparison rendering for Streamlit.

Built with HTML/CSS via st.markdown rather than a charting library: this is
fundamentally a styled card with a track + positioned dots/ticks, and a real
chart lib would add a dependency and a rendering pipeline for no benefit here.

A linear fill-bar cannot show a tiny (<0.1%) tokenized fraction of a huge total —
the fill is imperceptible regardless of labeling tricks. Instead, the percentage
and dollar figures are shown as a large headline stat, and a secondary log-scale
bar (with order-of-magnitude gridlines, so it visibly reads as log rather than an
arbitrary line) plots tokenized vs. total on a shared axis. The literal numbers
are always also stated in a plain text caption, so they're never conveyed by
pixel position alone.

Per-asset visual identity (accent color + icon) lives in `_ASSET_THEME` below,
keyed by the same `asset_class` slug used in `registry.py` — add an entry there
when a new asset class is registered; unthemed asset classes fall back to
`_DEFAULT_THEME` so nothing breaks if a theme entry is missed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import streamlit as st

from reality_check.models import AssetClassResult

_MAX_LOG_TICKS = 8


@dataclass(frozen=True)
class _Theme:
    accent: str
    icon_svg: str
    track_gradient: str


def _coin_icon(color: str) -> str:
    return (
        f'<svg viewBox="0 0 24 24" width="28" height="28">'
        f'<circle cx="12" cy="12" r="10" fill="{color}" opacity="0.15"/>'
        f'<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="2"/>'
        f'<circle cx="12" cy="12" r="5.5" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f"</svg>"
    )


def _bank_icon(color: str) -> str:
    return (
        f'<svg viewBox="0 0 24 24" width="28" height="28">'
        f'<polygon points="12,3 21,9 3,9" fill="{color}"/>'
        f'<rect x="4" y="10" width="2.5" height="8" fill="{color}"/>'
        f'<rect x="9" y="10" width="2.5" height="8" fill="{color}"/>'
        f'<rect x="14" y="10" width="2.5" height="8" fill="{color}"/>'
        f'<rect x="18.5" y="10" width="2.5" height="8" fill="{color}"/>'
        f'<rect x="3" y="19" width="18" height="1.8" fill="{color}"/>'
        f"</svg>"
    )


_DEFAULT_TRACK_GRADIENT = "rgba(127, 127, 127, 0.2)"

_DEFAULT_THEME = _Theme(
    accent="#8a8a8a", icon_svg=_coin_icon("#8a8a8a"), track_gradient=_DEFAULT_TRACK_GRADIENT
)

_ASSET_THEME: dict[str, _Theme] = {
    "gold": _Theme(
        accent="#b8860b",
        icon_svg=_coin_icon("#b8860b"),
        # muted-brass -> polished-gold -> pale-gold, evoking gold tones along the track
        track_gradient="linear-gradient(90deg, #a67c00 0%, #d4af37 55%, #f6e6b4 100%)",
    ),
    "treasuries": _Theme(
        accent="#2b6cb0",
        icon_svg=_bank_icon("#2b6cb0"),
        # navy -> mid-blue -> pale-blue, evoking US Treasury/government-bond tones
        track_gradient="linear-gradient(90deg, #1e3a5f 0%, #2b6cb0 55%, #a9c6e8 100%)",
    ),
}


def inject_base_css() -> None:
    st.markdown(
        """
        <style>
        .rc-accent-bar {
            height: 4px;
            width: 100%;
            border-radius: 3px;
            margin-bottom: 0.9rem;
        }
        .rc-card-header {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            margin-bottom: 0.4rem;
        }
        .rc-icon-badge {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(127, 127, 127, 0.1);
            flex-shrink: 0;
        }
        .rc-card-title { font-size: 1.15rem; font-weight: 700; }
        .rc-hero { margin: 0.25rem 0 0.5rem 0; }
        .rc-hero-pct { font-size: 2.5rem; font-weight: 700; line-height: 1.1; }
        .rc-hero-sub { font-size: 1rem; color: rgba(127, 127, 127, 0.9); }
        .rc-breakdown {
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            margin: 0.6rem 0 0.4rem 0;
            padding: 0.7rem 0.9rem;
            background: rgba(127, 127, 127, 0.06);
            border-radius: 8px;
        }
        .rc-breakdown-item:not(:last-child) {
            padding-bottom: 0.6rem;
            border-bottom: 1px solid rgba(127, 127, 127, 0.15);
        }
        .rc-breakdown-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
        }
        .rc-breakdown-name { font-weight: 600; }
        .rc-breakdown-value { font-weight: 600; }
        .rc-breakdown-backing {
            font-size: 0.78rem;
            color: rgba(127, 127, 127, 0.85);
            margin-top: 0.2rem;
            line-height: 1.4;
        }
        .rc-log-wrap { position: relative; margin: 2rem 0.25rem 2.6rem 0.25rem; }
        .rc-log-track {
            position: relative;
            height: 6px;
            background: rgba(127, 127, 127, 0.2);
            border-radius: 3px;
        }
        .rc-log-tick {
            position: absolute;
            top: 0;
            width: 1px;
            height: 6px;
            background: rgba(127, 127, 127, 0.45);
        }
        .rc-log-tick-label {
            position: absolute;
            top: 12px;
            transform: translateX(-50%);
            font-size: 0.65rem;
            color: rgba(127, 127, 127, 0.75);
            white-space: nowrap;
        }
        .rc-log-dot {
            position: absolute;
            top: 50%;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            transform: translate(-50%, -50%);
        }
        .rc-log-dot-label {
            position: absolute;
            bottom: calc(100% + 6px);
            transform: translateX(-50%);
            font-size: 0.8rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .rc-log-caption {
            font-size: 0.72rem;
            color: rgba(127, 127, 127, 0.75);
            margin-top: 1.7rem;
            text-align: center;
        }
        .rc-stale-badge {
            font-size: 0.75rem;
            color: #b7791f;
        }
        .rc-header {
            position: relative;
            left: 50%;
            right: 50%;
            margin-left: -50vw;
            margin-right: -50vw;
            width: 100vw;
            background: #111827;
            color: #ffffff;
            padding: 2rem max(1.5rem, calc(50vw - 350px));
            margin-bottom: 2rem;
        }
        .rc-header-title { font-size: 1.8rem; font-weight: 700; margin: 0; }
        .rc-header-sub { font-size: 1rem; color: rgba(255, 255, 255, 0.7); margin-top: 0.3rem; }
        div[data-testid="stAppViewContainer"] .block-container,
        div[data-testid="stAppViewContainer"] .stMainBlockContainer {
            padding-top: 1.5rem;
        }
        header[data-testid="stHeader"] {
            background: #111827;
        }
        header[data-testid="stHeader"] * {
            color: #ffffff !important;
            fill: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="rc-header">'
        f'<div class="rc-header-title">{title}</div>'
        f'<div class="rc-header-sub">{subtitle}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_asset_bar(
    result: AssetClassResult,
    key: str,
    methodology: str,
    quantity: tuple[str, str] | None = None,
) -> bool:
    label = key.replace("_", " ").title()
    theme = _ASSET_THEME.get(key, _DEFAULT_THEME)

    with st.container(border=True):
        st.markdown(
            f'<div class="rc-accent-bar" style="background: {theme.accent};"></div>'
            f'<div class="rc-card-header">'
            f'<div class="rc-icon-badge">{theme.icon_svg}</div>'
            f'<div class="rc-card-title">{label}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        modes = ["%", "$"] + (["mass"] if quantity else [])
        mode = st.radio(
            "Display as", modes, horizontal=True, key=f"mode_{key}", label_visibility="collapsed"
        )
        st.markdown(_hero_html(result, label, theme.accent, mode, quantity), unsafe_allow_html=True)

        breakdown = _breakdown_html(result, mode)
        if breakdown:
            st.markdown(breakdown, unsafe_allow_html=True)

        log_bar = _log_scale_bar_html(result, theme.accent, theme.track_gradient)
        if log_bar:
            st.markdown(log_bar, unsafe_allow_html=True)

        st.caption(
            f"Tokenized {label}: {_format_usd(result.tokenized_usd)} / "
            f"{_format_usd(result.total.value_usd)} total = {_format_pct(result.pct_tokenized)}"
            + (" ⚠ stale (fallback data in use)" if result.is_stale() else "")
        )
        with st.expander("How is this calculated?"):
            st.markdown(methodology)
            if result.source_notes:
                st.divider()
                st.caption(f"Latest verification: {result.source_notes}")

        clicked = st.button("Refresh", key=f"refresh_{key}")

    return clicked


def _hero_html(
    result: AssetClassResult,
    label: str,
    accent: str,
    mode: str,
    quantity: tuple[str, str] | None,
) -> str:
    pct = _format_pct(result.pct_tokenized)
    if mode == "mass" and quantity:
        tokenized_qty, total_qty = quantity
        headline = tokenized_qty
        sub = f"tokenized of {total_qty} total {label.lower()} ({pct})"
    elif mode == "$":
        headline = _format_usd(result.tokenized_usd)
        sub = f"tokenized of {_format_usd(result.total.value_usd)} total {label.lower()} ({pct})"
    else:
        headline = pct
        sub = (
            f"{_format_usd(result.tokenized_usd)} tokenized of "
            f"{_format_usd(result.total.value_usd)} total {label.lower()}"
        )
    return (
        '<div class="rc-hero">'
        f'<div class="rc-hero-pct" style="color: {accent};">{headline}</div>'
        f'<div class="rc-hero-sub">{sub}</div>'
        "</div>"
    )


def _breakdown_html(result: AssetClassResult, mode: str) -> str | None:
    # No per-component weight data in "mass" mode (only an aggregate tokenized/total
    # pair is available there), so the breakdown only applies to %/$ display.
    if mode == "mass" or len(result.components) < 2:
        return None
    rows = "".join(
        f'<div class="rc-breakdown-item">'
        f'<div class="rc-breakdown-row">'
        f'<span class="rc-breakdown-name">{c.display_name or c.symbol}</span>'
        f'<span class="rc-breakdown-value">{_format_usd(c.value_usd)}</span>'
        f"</div>"
        + (f'<div class="rc-breakdown-backing">Backed by: {c.backing}</div>' if c.backing else "")
        + "</div>"
        for c in result.components
    )
    return f'<div class="rc-breakdown">{rows}</div>'


def _log_scale_bar_html(result: AssetClassResult, accent: str, track_gradient: str) -> str | None:
    tokenized = result.tokenized_usd
    total = result.total.value_usd
    if tokenized <= 0 or total <= 0:
        return None

    log_min = math.floor(math.log10(tokenized))
    log_max = math.ceil(math.log10(total))
    if log_max <= log_min:
        log_max = log_min + 1
    span = log_max - log_min

    def position(value: float) -> float:
        return (math.log10(value) - log_min) / span * 100

    step = max(1, math.ceil(span / _MAX_LOG_TICKS))
    ticks = list(range(log_min, log_max, step)) + [log_max]

    ticks_html = "".join(
        f'<div class="rc-log-tick" style="left: {(t - log_min) / span * 100}%;"></div>'
        f'<div class="rc-log-tick-label" style="left: {(t - log_min) / span * 100}%;">'
        f"{_format_usd(10 ** t)}</div>"
        for t in ticks
    )

    tokenized_pos = position(tokenized)
    total_pos = position(total)

    return (
        '<div class="rc-log-wrap"><div class="rc-log-track" '
        f'style="background: {track_gradient};">'
        f"{ticks_html}"
        f'<div class="rc-log-dot" style="left: {tokenized_pos}%; background: {accent};"></div>'
        f'<div class="rc-log-dot" style="left: {total_pos}%; background: rgba(127, 127, 127, 0.7);"></div>'
        f'<div class="rc-log-dot-label" style="left: {tokenized_pos}%; color: {accent};">Tokenized</div>'
        f'<div class="rc-log-dot-label" style="left: {total_pos}%;">Total</div>'
        "</div>"
        '<div class="rc-log-caption">log scale — linear would make this invisible</div>'
        "</div>"
    )


def _format_usd(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1e12:
        return f"${value / 1e12:.1f}T"
    if abs_value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if abs_value >= 1e6:
        return f"${value / 1e6:.1f}M"
    return f"${value:,.0f}"


def _format_pct(value: float) -> str:
    if value == 0:
        return "0%"
    if value < 0.001:
        return f"{value:.5f}%"
    if value < 1:
        return f"{value:.3f}%"
    return f"{value:.2f}%"
