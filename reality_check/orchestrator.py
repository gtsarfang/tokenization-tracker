"""Glues a source's live fetch to calculation and storage. The only module that
knows about both `sources` and `storage`."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from reality_check import calc, storage
from reality_check.interfaces import AssetClassSource
from reality_check.models import AssetClassResult, ComponentValue, TotalValue


def refresh_asset_class(
    source: AssetClassSource, conn: sqlite3.Connection
) -> AssetClassResult:
    components = source.fetch_tokenized()
    total = source.fetch_total()
    result = calc.build_asset_class_result(
        source.asset_class,
        components,
        total,
        datetime.now(timezone.utc),
        _build_source_notes(components, total),
    )
    storage.insert_snapshot(conn, result)
    return result


def _build_source_notes(components: tuple[ComponentValue, ...], total: TotalValue) -> str:
    component_notes = [f"{c.symbol}: {c.note}" for c in components if c.note]
    parts = [total.basis_note, *component_notes]
    return " | ".join(parts)
