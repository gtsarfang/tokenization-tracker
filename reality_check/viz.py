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
from collections.abc import Iterable
from dataclasses import dataclass

import streamlit as st

from reality_check.models import AssetClassResult, DataQuality

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
    "silver": _Theme(
        accent="#71797E",
        icon_svg=_coin_icon("#71797E"),
        # gunmetal -> silver -> near-white, evoking silver tones along the track
        track_gradient="linear-gradient(90deg, #52585c 0%, #a8adb2 55%, #e8eaec 100%)",
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
        .rc-card-header {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            margin-bottom: 0.2rem;
        }
        .rc-icon-badge {
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(127, 127, 127, 0.1);
            flex-shrink: 0;
        }
        .rc-icon-badge svg { width: 16px; height: 16px; }
        .rc-card-title { font-size: 1.05rem; font-weight: 700; }
        .rc-hero { margin: 0.05rem 0 0.15rem 0; }
        .rc-hero-pct { font-size: 1.5rem; font-weight: 700; line-height: 1.1; }
        .rc-hero-sub { font-size: 0.76rem; color: rgba(127, 127, 127, 0.9); }
        .rc-hero-alt { font-size: 0.68rem; color: rgba(127, 127, 127, 0.75); margin-top: 0.05rem; }
        .rc-breakdown {
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
            margin: 0.3rem 0 0.15rem 0;
            padding: 0.4rem 0.6rem;
            background: rgba(127, 127, 127, 0.06);
            border-radius: 8px;
        }
        .rc-breakdown-item:not(:last-child) {
            padding-bottom: 0.3rem;
            border-bottom: 1px solid rgba(127, 127, 127, 0.15);
        }
        .rc-breakdown-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.78rem;
        }
        .rc-breakdown-name { font-weight: 600; }
        .rc-breakdown-value { font-weight: 600; }
        .rc-breakdown-backing {
            font-size: 0.68rem;
            color: rgba(127, 127, 127, 0.85);
            margin-top: 0.1rem;
            line-height: 1.3;
        }
        .rc-scale-caption {
            font-size: 0.62rem;
            color: rgba(127, 127, 127, 0.65);
            margin-top: 1.3rem;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .rc-log-wrap { position: relative; margin: 1.3rem 0.25rem 0.3rem 0.25rem; }
        .rc-log-track {
            position: relative;
            height: 6px;
            border-radius: 3px;
            overflow: hidden;
        }
        /* Exact same box as .rc-log-track (top:0, full width, 6px tall), but
        without overflow:hidden — dots/labels live here instead of inside the
        track so they aren't clipped, while still sharing the track's geometry
        for `top: 50%` / `left: X%` to resolve correctly. */
        .rc-log-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 6px;
        }
        .rc-log-fill {
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
        }
        .rc-log-remainder {
            position: absolute;
            top: 0;
            height: 100%;
            background: rgba(127, 127, 127, 0.15);
        }
        .rc-log-tick {
            position: absolute;
            top: -3px;
            width: 1px;
            height: 12px;
            background: rgba(0, 0, 0, 0.35);
        }
        .rc-log-tick-label {
            position: absolute;
            top: 12px;
            transform: translateX(-50%);
            font-size: 0.65rem;
            color: rgba(127, 127, 127, 0.8);
            white-space: nowrap;
        }
        .rc-tick-label-start { transform: translateX(0); }
        .rc-tick-label-end { transform: translateX(-100%); }
        .rc-log-dot {
            position: absolute;
            top: 50%;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            border: 2px solid #ffffff;
        }
        .rc-log-dot-label {
            position: absolute;
            bottom: calc(100% + 6px);
            transform: translateX(-50%);
            font-size: 0.8rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .rc-log-dot-label-end {
            transform: translateX(-100%);
        }
        /* Smaller, muted marker for a secondary reference point (e.g. gold/
        silver's "investment stock" figure) — label sits below the track so
        it never collides with the Tokenized/Total labels above it. */
        .rc-log-dot-sub {
            position: absolute;
            top: 50%;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            border: 2px solid #ffffff;
            background: rgba(127, 127, 127, 0.6);
        }
        .rc-log-dot-label-sub {
            position: absolute;
            top: 22px;
            transform: translateX(-50%);
            font-size: 0.62rem;
            font-weight: 600;
            color: rgba(127, 127, 127, 0.85);
            white-space: nowrap;
        }
        .rc-multiplier-callout {
            font-size: 0.7rem;
            font-weight: 600;
            color: rgba(127, 127, 127, 0.9);
            margin-top: 0.3rem;
            text-align: center;
        }
        .rc-stale-badge {
            font-size: 0.75rem;
            color: #b7791f;
        }
        .rc-manual-tag {
            font-size: 0.62rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            color: rgba(127, 127, 127, 0.9);
            background: rgba(127, 127, 127, 0.12);
            border-radius: 4px;
            padding: 0.05rem 0.35rem;
            margin-left: 0.4rem;
            vertical-align: middle;
        }
        .rc-header {
            background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
            color: #ffffff;
            padding: 1rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 0.8rem;
        }
        .rc-header-title {
            font-size: 1.6rem;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.02em;
        }
        .rc-header-sub { font-size: 0.82rem; color: rgba(255, 255, 255, 0.65); margin-top: 0.15rem; }
        div[data-testid="stAppViewContainer"] .block-container,
        div[data-testid="stAppViewContainer"] .stMainBlockContainer {
            /* Tighter than Streamlit's default, but not so tight that our
            header clips under Streamlit Community Cloud's own toolbar
            (the Share/star/GitHub icon row it injects above the app on
            hosted deployments only — not present when running locally). */
            padding-top: 3rem;
        }
        div[data-testid="stHorizontalBlock"] {
            align-items: stretch;
        }
        /* Safety net for narrow (phone) viewports: the log-scale bar's dot/tick
        labels are absolutely positioned by percentage with nowrap text, sized
        for a desktop-width column — on a narrow screen a long label (e.g.
        "Tokenized ($10.6B)") can run past the card edge. overflow-x: hidden
        here prevents that from turning into a page-wide horizontal scrollbar;
        the media query below shrinks those labels so it's less likely to
        happen in the first place. */
        div[data-testid="stAppViewContainer"] {
            overflow-x: hidden;
        }
        @media (max-width: 480px) {
            .rc-header-title { font-size: 1.3rem; }
            .rc-hero-pct { font-size: 1.2rem; }
            .rc-log-dot-label, .rc-log-dot-label-sub, .rc-log-tick-label {
                font-size: 0.56rem;
            }
        }
        /* Compact Streamlit's own chrome — dividers, the display-mode control,
        and the expander — so the three sections have a shot at fitting in one
        screen alongside the header, instead of Streamlit's default spacing
        (built for a handful of widgets, not a dense stacked layout) piling up. */
        div[data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] {
            gap: 0.4rem;
        }
        hr { margin: 0.2rem 0 !important; }
        div[data-testid="stExpander"] { margin-top: 0.2rem; }
        div[data-testid="stExpander"] summary { padding: 0.3rem 0.6rem; min-height: 0; }
        div[data-testid="stCaptionContainer"] { margin-top: 0.1rem; }
        div[data-testid="stButtonGroup"] { margin-bottom: 0; }
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


_ASSET_LABELS: dict[str, str] = {
    # Treasuries is specifically US-scoped (US Treasury debt) — spelled out in
    # the label so it's not mistaken for a global figure, unlike Gold/Silver.
    "treasuries": "US Treasuries",
}


def render_asset_section(
    result: AssetClassResult,
    key: str,
    methodology: str,
    quantity: tuple[str, str] | None = None,
    mode: str = "%",
    shared_log_span: float | None = None,
) -> None:
    label = _ASSET_LABELS.get(key, key.replace("_", " ").title())
    theme = _ASSET_THEME.get(key, _DEFAULT_THEME)

    container_key = f"rc-section-{key}"
    with st.container(key=container_key):
        st.markdown(
            f'<style>.st-key-{container_key} {{ '
            f"border-left: 4px solid {theme.accent}; padding: 0.2rem 0 0.2rem 1.5rem; "
            "}</style>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="rc-card-header">'
            f'<div class="rc-icon-badge">{theme.icon_svg}</div>'
            f'<div class="rc-card-title">{label}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(_hero_html(result, label, theme.accent, mode, quantity), unsafe_allow_html=True)

        left, right = st.columns([2, 3], gap="medium")
        with left:
            breakdown = _breakdown_html(result)
            if breakdown:
                st.markdown(breakdown, unsafe_allow_html=True)
        with right:
            log_bar = _log_scale_bar_html(result, theme.accent, theme.track_gradient, shared_log_span)
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

    st.divider()


def _hero_html(
    result: AssetClassResult,
    label: str,
    accent: str,
    mode: str,
    quantity: tuple[str, str] | None,
) -> str:
    pct = _format_pct(result.pct_tokenized)
    # "unit" means "this asset class's natural physical unit" (troy oz for
    # gold/silver) where one exists. Treasuries has none — it's natively
    # dollar-denominated — so "unit" there just means $, not a silent fall
    # back to % (which "unit" wouldn't suggest to anyone).
    if mode == "unit" and quantity:
        tokenized_qty, total_qty = quantity
        headline = tokenized_qty
        sub = f"tokenized of {total_qty} total {label.lower()} ({pct})"
    elif mode == "$" or mode == "unit":
        headline = _format_usd(result.tokenized_usd)
        sub = f"tokenized of {_format_usd(result.total.value_usd)} total {label.lower()} ({pct})"
    else:
        headline = pct
        sub = (
            f"{_format_usd(result.tokenized_usd)} tokenized of "
            f"{_format_usd(result.total.value_usd)} total {label.lower()}"
        )
    alt_line = ""
    if result.alt_total is not None and result.alt_pct_tokenized is not None:
        alt_line = (
            '<div class="rc-hero-alt">'
            f"vs. investment stock only: {_format_pct(result.alt_pct_tokenized)}"
            "</div>"
        )
    return (
        '<div class="rc-hero">'
        f'<div class="rc-hero-pct" style="color: {accent};">{headline}</div>'
        f'<div class="rc-hero-sub">{sub}</div>'
        f"{alt_line}"
        "</div>"
    )


def _breakdown_html(result: AssetClassResult) -> str | None:
    # Always shown regardless of display mode (%/$/unit) — this is supplementary
    # per-component detail (including what backs each token), not tied to the
    # headline's unit. Shown for single-component assets too, not just 2+ — the
    # "Backed by" text is the whole point, not a comparison between components.
    # Sized to however many components this asset class actually has — no padding
    # to match other cards, since a fake empty row was worse than cards simply
    # differing in height.
    if not result.components:
        return None
    sorted_components = sorted(result.components, key=lambda c: c.value_usd, reverse=True)
    rows = "".join(
        f'<div class="rc-breakdown-item">'
        f'<div class="rc-breakdown-row">'
        f'<span class="rc-breakdown-name">{c.display_name or c.symbol}'
        # A permanent, deliberate choice (no live source exists) — distinct
        # from the card-level "stale" badge, which should mean "this
        # normally-live figure happens to be out of date right now."
        + (
            ' <span class="rc-manual-tag" title="No live API available for this '
            'figure — manually maintained, refreshed periodically.">manually '
            "tracked</span>"
            if c.supply_quality is DataQuality.MANUAL or c.price_quality is DataQuality.MANUAL
            else ""
        )
        + "</span>"
        f'<span class="rc-breakdown-value">{_format_usd(c.value_usd)}</span>'
        f"</div>"
        + (f'<div class="rc-breakdown-backing">Backed by: {c.backing}</div>' if c.backing else "")
        + "</div>"
        for c in sorted_components
    )
    return f'<div class="rc-breakdown">{rows}</div>'


def _tick_align_class(fraction: float) -> str:
    if fraction <= 0.0:
        return "rc-tick-label-start"
    if fraction >= 1.0:
        return "rc-tick-label-end"
    return ""


def _format_multiplier(ratio: float) -> str:
    if ratio >= 100:
        return f"~{ratio:,.0f}x"
    if ratio >= 10:
        return f"~{ratio:.0f}x"
    return f"~{ratio:.1f}x"


def compute_shared_log_span(results: Iterable[AssetClassResult]) -> float:
    # Each card's own natural span (decades between its tokenized fraction and
    # its Total) differs slightly from the others, which shifted where ticks
    # landed card to card (one showing a 0.01% tick, another starting at
    # 0.1%) even though the underlying fractions were similar magnitude —
    # making the bars look inconsistent when they were actually close. Using
    # the largest natural span for every card's tick range (while still
    # anchoring each card's own Total at the right edge) keeps tick positions
    # aligned across cards, so equal pixel distance means equal multiplicative
    # gap on every bar.
    spans = []
    for result in results:
        tokenized, total = result.tokenized_usd, result.total.value_usd
        if tokenized <= 0 or total <= 0:
            continue
        log_min = math.floor(math.log10(tokenized))
        log_max = math.log10(total)
        spans.append(max(log_max - log_min, 1.0))
    return max(spans) if spans else 1.0


def _log_scale_bar_html(
    result: AssetClassResult, accent: str, track_gradient: str, shared_span: float | None = None
) -> str | None:
    tokenized = result.tokenized_usd
    total = result.total.value_usd
    if tokenized <= 0 or total <= 0:
        return None

    # Not rounded up to the next power of 10 — the track ends exactly at Total,
    # like a loading bar, rather than continuing past it to a clean gridline.
    log_max = math.log10(total)
    span = shared_span if shared_span is not None else max(log_max - math.floor(math.log10(tokenized)), 1.0)
    log_min = log_max - span

    def position(value: float) -> float:
        return (math.log10(value) - log_min) / span * 100

    # Ticks are round percentages of Total (..., 0.01%, 0.1%, 1%, 10%, 100%)
    # rather than round dollar amounts, so every card reads on the same,
    # familiar scale regardless of its total's dollar magnitude. 100% is
    # Total itself (log_max), so the tick exponent k maps to log10($) as
    # log_max + (k - 2).
    k_max = 2
    k_min = math.ceil(log_min - log_max + 2)
    step = max(1, math.ceil((k_max - k_min) / _MAX_LOG_TICKS))
    tick_ks = list(range(k_min, k_max, step)) + [k_max]
    ticks_html = "".join(
        f'<div class="rc-log-tick" style="left: {(log_max + (k - 2) - log_min) / span * 100}%;"></div>'
        f'<div class="rc-log-tick-label '
        f'{_tick_align_class((log_max + (k - 2) - log_min) / span)}" '
        f'style="left: {(log_max + (k - 2) - log_min) / span * 100}%;">{_format_pct(10 ** k)}</div>'
        for k in tick_ks
    )

    tokenized_pos = position(tokenized)
    total_pos = 100.0

    alt_html = ""
    if result.alt_total is not None and result.alt_total.value_usd > 0:
        alt_pos = position(result.alt_total.value_usd)
        alt_html = (
            f'<div class="rc-log-dot-sub" style="left: {alt_pos}%;"></div>'
            f'<div class="rc-log-dot-label-sub" style="left: {alt_pos}%;">'
            f"Investment stock ({_format_usd(result.alt_total.value_usd)})</div>"
        )

    return (
        '<div class="rc-log-wrap"><div class="rc-log-track">'
        f'<div class="rc-log-fill" style="width: {tokenized_pos}%; background: {track_gradient};"></div>'
        f'<div class="rc-log-remainder" style="left: {tokenized_pos}%; '
        f'width: {100 - tokenized_pos}%;"></div>'
        "</div>"
        # Dots and dot-labels live in .rc-log-overlay, a sibling of the track
        # sharing its exact box (top:0, 6px tall) but without overflow:hidden
        # (needed on the track itself to clip the fill/remainder to its
        # rounded corners) — that's what previously clipped/mispositioned
        # labels here. Ticks are separate wrap-level siblings, unaffected.
        '<div class="rc-log-overlay">'
        f'<div class="rc-log-dot" style="left: {tokenized_pos}%; background: {accent};"></div>'
        f'<div class="rc-log-dot" style="left: {total_pos}%; background: rgba(127, 127, 127, 0.7);"></div>'
        f'<div class="rc-log-dot-label" style="left: {tokenized_pos}%; color: {accent};">'
        f"Tokenized ({_format_usd(tokenized)})</div>"
        f'<div class="rc-log-dot-label rc-log-dot-label-end" style="left: {total_pos}%;">'
        f"Total ({_format_usd(total)})</div>"
        f"{alt_html}"
        "</div>"
        f"{ticks_html}"
        '<div class="rc-scale-caption">Log scale</div>'
        f'<div class="rc-multiplier-callout">Total is {_format_multiplier(total / tokenized)} '
        "larger than what's tokenized</div>"
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
