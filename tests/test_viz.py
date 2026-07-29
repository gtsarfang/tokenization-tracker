"""Checks on the comparison chart's log-axis positioning.

Bar widths are the whole point of that chart — if the axis math is wrong the
page still renders happily and just shows a misleading ranking, so this is the
one piece of viz worth a test.
"""

import dataclasses
import re
from datetime import datetime, timezone

from reality_check.models import AssetClassResult, DataQuality, TotalValue
from reality_check.viz import _comparison_chart_html, _log_scale_bar_html


def _result(pct: float, tokenized: float, total: float) -> AssetClassResult:
    return AssetClassResult(
        asset_class="x",
        tokenized_usd=tokenized,
        total=TotalValue(value_usd=total, basis_note="t", quality=DataQuality.LIVE),
        pct_tokenized=pct,
        components=(),
        as_of=datetime.now(timezone.utc),
        source_notes="",
    )


def _widths(html: str) -> list[float]:
    return [float(w) for w in re.findall(r'rc-cmp-fill" style="width: ([\d.]+)%', html)]


def test_bar_order_matches_pct_order() -> None:
    html = _comparison_chart_html(
        {
            "gold": _result(0.018, 4.9e9, 28e12),
            "silver": _result(0.008, 238e6, 3.1e12),
            "treasuries": _result(0.045, 14.5e9, 31e12),
        }
    )
    gold, silver, treasuries = _widths(html)
    assert silver < gold < treasuries


def test_widths_stay_within_the_track() -> None:
    html = _comparison_chart_html(
        {"a": _result(0.008, 1.0, 2.0), "b": _result(100.0, 1.0, 1.0)}
    )
    widths = _widths(html)
    assert all(0 <= w <= 100 for w in widths)
    # 100% tokenized is the axis maximum, so it fills the track exactly.
    assert widths[1] == 100.0


def test_equal_ratios_are_equal_distances() -> None:
    """A log axis means a 10x gap is the same pixel gap wherever it sits."""
    html = _comparison_chart_html(
        {
            "a": _result(0.01, 1.0, 1.0),
            "b": _result(0.1, 1.0, 1.0),
            "c": _result(1.0, 1.0, 1.0),
        }
    )
    a, b, c = _widths(html)
    assert abs((b - a) - (c - b)) < 0.01


def test_toggle_switches_units_and_never_the_share() -> None:
    """The share is the headline in every mode — the toggle only changes the
    unit of the amounts under it, and never the bar geometry."""
    results = {"gold": _result(0.018, 4.9e9, 28e12)}
    quantities = {"gold": ("143.1 t", "6.7M t", None)}
    usd_html = _comparison_chart_html(results, "$", quantities)
    unit_html = _comparison_chart_html(results, "unit", quantities)

    assert _widths(usd_html) == _widths(unit_html)
    assert ">0.018%<" in usd_html and ">0.018%<" in unit_html
    assert "$4.9B of $28.0T" in usd_html
    assert "143.1 t of 6.7M t" in unit_html


def test_unit_mode_falls_back_to_usd_without_a_natural_unit() -> None:
    # Treasuries has no physical unit, so it stays in dollars rather than
    # showing a weight it can't express.
    html = _comparison_chart_html({"treasuries": _result(0.045, 14.5e9, 31e12)}, "unit", {"treasuries": None})
    assert "$14.5B of $31.0T" in html


def test_alt_marker_gets_its_clearance_class() -> None:
    """The sub-label row is absolutely positioned, so the caption below only
    clears it when this class is present — without it they overlap."""
    alt = TotalValue(value_usd=523.2e9, basis_note="etf", quality=DataQuality.LIVE)
    with_alt = dataclasses.replace(
        _result(0.018, 4.9e9, 28e12), alt_total=alt, alt_pct_tokenized=0.945
    )
    html = _log_scale_bar_html(with_alt, "#b8860b", "none", 5.0, "Gold")
    assert "rc-log-wrap-alt" in html
    # Labeled as a share of Total ($523.2B of $28.0T), matching the axis this
    # marker sits on — not as tokenized-over-investment-stock (0.945%), which
    # would put a number on the label that disagrees with the marker position.
    assert "(1.87%)" in html
    assert "0.945%" not in html

    without_alt = _result(0.045, 14.5e9, 31e12)
    assert "rc-log-wrap-alt" not in _log_scale_bar_html(without_alt, "#2b6cb0", "none", 5.0, "T")


def test_no_positive_values_renders_nothing() -> None:
    assert _comparison_chart_html({"a": _result(0.0, 0.0, 1.0)}) == ""
