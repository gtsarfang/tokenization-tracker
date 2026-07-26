from datetime import datetime, timezone

import pytest

from reality_check.calc import (
    build_asset_class_result,
    compute_pct_tokenized,
    sum_component_values,
)
from reality_check.models import ComponentValue, DataQuality, TotalValue


class TestComputePctTokenized:
    def test_normal_case(self) -> None:
        pct = compute_pct_tokenized(5_200_000_000, 20_100_000_000_000)
        assert pct == pytest.approx(0.02587, rel=1e-3)

    def test_full_tokenization(self) -> None:
        assert compute_pct_tokenized(100.0, 100.0) == 100.0

    @pytest.mark.parametrize(
        ("tokenized_usd", "total_usd"),
        [
            (100.0, 0.0),
            (100.0, -50.0),
            (None, 100.0),
            (100.0, None),
            (None, None),
            (-10.0, 100.0),
        ],
    )
    def test_edge_cases_resolve_to_zero(
        self, tokenized_usd: float | None, total_usd: float | None
    ) -> None:
        assert compute_pct_tokenized(tokenized_usd, total_usd) == 0.0

    def test_tokenized_exceeds_total_clamped(self) -> None:
        assert compute_pct_tokenized(150.0, 100.0) == 100.0


class TestSumComponentValues:
    def test_normal_sum(self) -> None:
        components = [
            ComponentValue(
                symbol="PAXG",
                quantity=1.0,
                unit_price_usd=1.0,
                value_usd=1.0,
                supply_quality=DataQuality.LIVE,
                price_quality=DataQuality.LIVE,
            ),
            ComponentValue(
                symbol="XAUT",
                quantity=2.0,
                unit_price_usd=1.0,
                value_usd=2.0,
                supply_quality=DataQuality.LIVE,
                price_quality=DataQuality.LIVE,
            ),
        ]
        assert sum_component_values(components) == 3.0

    def test_empty_iterable(self) -> None:
        assert sum_component_values([]) == 0.0


class TestBuildAssetClassResult:
    def test_computes_pct_and_preserves_as_of(self) -> None:
        components = (
            ComponentValue(
                symbol="PAXG",
                quantity=10.0,
                unit_price_usd=5.0,
                value_usd=50.0,
                supply_quality=DataQuality.LIVE,
                price_quality=DataQuality.LIVE,
            ),
        )
        total = TotalValue(value_usd=500.0, basis_note="test basis", quality=DataQuality.LIVE)
        as_of = datetime(2026, 7, 25, tzinfo=timezone.utc)

        result = build_asset_class_result(
            "gold", components, total, as_of, "test source notes"
        )

        assert result.tokenized_usd == 50.0
        assert result.pct_tokenized == 10.0
        assert result.as_of == as_of
        assert result.source_notes == "test source notes"
