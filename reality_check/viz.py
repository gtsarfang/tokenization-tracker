"""Horizontal fill-bar rendering for Streamlit.

Built with HTML/CSS via st.markdown rather than a charting library: the visual is
fundamentally two styled <div>s (track + fill), and a real chart lib would add a
dependency and a rendering pipeline for no benefit here.

Below LABEL_OUTSIDE_THRESHOLD_PCT, the tokenized fill is too thin to hold a legible
label, so the percentage is pinned outside the bar with a leader line anchored at the
true fill edge — the label's horizontal position is separately clamped so it never
clips at the container edges. The literal numbers are always also stated in a plain
text caption, so they're never conveyed by pixel width alone.
"""

from __future__ import annotations

import streamlit as st

from reality_check.models import AssetClassResult, DataQuality

LABEL_OUTSIDE_THRESHOLD_PCT: float = 2.0

# Rendering floor so a sub-pixel sliver still paints a visible line. This does not
# change the reported percentage — only the width the fill div renders at.
_MIN_FILL_WIDTH_PX = 2

_CALLOUT_CLAMP_MIN_PCT = 6.0
_CALLOUT_CLAMP_MAX_PCT = 94.0


def inject_base_css() -> None:
    st.markdown(
        """
        <style>
        .rc-bar-wrap { position: relative; margin: 2.5rem 0 1rem 0; }
        .rc-bar-track {
            position: relative;
            height: 28px;
            background: rgba(127, 127, 127, 0.18);
            border-radius: 4px;
            overflow: visible;
        }
        .rc-bar-fill {
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            border-radius: 4px;
            background: #2b6cb0;
        }
        .rc-leader-line {
            position: absolute;
            bottom: 100%;
            width: 1px;
            height: 22px;
            background: rgba(127, 127, 127, 0.7);
        }
        .rc-callout {
            position: absolute;
            bottom: calc(100% + 24px);
            transform: translateX(-50%);
            white-space: nowrap;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .rc-inline-label {
            position: absolute;
            top: 0;
            height: 100%;
            display: flex;
            align-items: center;
            padding-left: 6px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .rc-stale-badge {
            font-size: 0.75rem;
            color: #b7791f;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_asset_bar(result: AssetClassResult, key: str) -> bool:
    label = key.replace("_", " ").title()
    st.markdown(f"**{label}**")
    st.markdown(_bar_html(result), unsafe_allow_html=True)
    st.caption(
        f"Tokenized {label}: {_format_usd(result.tokenized_usd)} / "
        f"{_format_usd(result.total.value_usd)} total = {_format_pct(result.pct_tokenized)}"
        + (" ⚠ stale (fallback data in use)" if result.is_stale() else "")
    )
    return st.button("Refresh", key=f"refresh_{key}")


def _bar_html(result: AssetClassResult) -> str:
    pct = result.pct_tokenized
    fill_width_style = f"width: max({_MIN_FILL_WIDTH_PX}px, {pct}%);"

    if pct < LABEL_OUTSIDE_THRESHOLD_PCT:
        callout_left = max(_CALLOUT_CLAMP_MIN_PCT, min(_CALLOUT_CLAMP_MAX_PCT, pct))
        label_html = (
            f'<div class="rc-leader-line" style="left: {pct}%;"></div>'
            f'<div class="rc-callout" style="left: {callout_left}%;">{_format_pct(pct)}</div>'
        )
    else:
        label_html = (
            f'<div class="rc-inline-label" style="left: {pct}%;">{_format_pct(pct)}</div>'
        )

    return (
        '<div class="rc-bar-wrap"><div class="rc-bar-track">'
        f'<div class="rc-bar-fill" style="{fill_width_style}"></div>'
        f"{label_html}"
        "</div></div>"
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
