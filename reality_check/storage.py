"""SQLite persistence for asset-class snapshots. Decoupled from ingestion/calc:
only knows about the models in `reality_check.models`."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from reality_check.models import AssetClassResult, ComponentValue, DataQuality, TotalValue

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_class       TEXT NOT NULL,
    tokenized_usd     REAL NOT NULL,
    total_usd         REAL NOT NULL,
    pct_tokenized     REAL NOT NULL,
    as_of_date        TEXT NOT NULL,
    total_basis_note  TEXT NOT NULL,
    total_quality     TEXT NOT NULL CHECK (total_quality IN ('live','fallback')),
    source_notes      TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_snapshots_asset_class_as_of
    ON snapshots (asset_class, as_of_date);

CREATE TABLE IF NOT EXISTS snapshot_components (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id      INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    symbol           TEXT NOT NULL,
    quantity         REAL NOT NULL,
    unit_price_usd   REAL NOT NULL,
    value_usd        REAL NOT NULL,
    supply_quality   TEXT NOT NULL CHECK (supply_quality IN ('live','fallback')),
    price_quality    TEXT NOT NULL CHECK (price_quality IN ('live','fallback')),
    note             TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_snapshot_components_snapshot_id
    ON snapshot_components (snapshot_id);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def insert_snapshot(conn: sqlite3.Connection, result: AssetClassResult) -> int:
    cursor = conn.execute(
        """
        INSERT INTO snapshots (
            asset_class, tokenized_usd, total_usd, pct_tokenized, as_of_date,
            total_basis_note, total_quality, source_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.asset_class,
            result.tokenized_usd,
            result.total.value_usd,
            result.pct_tokenized,
            result.as_of.isoformat(),
            result.total.basis_note,
            result.total.quality.value,
            result.source_notes,
        ),
    )
    snapshot_id = cursor.lastrowid
    assert snapshot_id is not None

    conn.executemany(
        """
        INSERT INTO snapshot_components (
            snapshot_id, symbol, quantity, unit_price_usd, value_usd,
            supply_quality, price_quality, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                snapshot_id,
                c.symbol,
                c.quantity,
                c.unit_price_usd,
                c.value_usd,
                c.supply_quality.value,
                c.price_quality.value,
                c.note,
            )
            for c in result.components
        ],
    )
    conn.commit()
    return snapshot_id


def fetch_latest_snapshot(conn: sqlite3.Connection, asset_class: str) -> AssetClassResult | None:
    rows = fetch_history(conn, asset_class, limit=1)
    return rows[0] if rows else None


def fetch_history(
    conn: sqlite3.Connection, asset_class: str, limit: int = 100
) -> list[AssetClassResult]:
    conn.row_factory = sqlite3.Row
    snapshot_rows = conn.execute(
        """
        SELECT * FROM snapshots
        WHERE asset_class = ?
        ORDER BY as_of_date DESC
        LIMIT ?
        """,
        (asset_class, limit),
    ).fetchall()

    results = []
    for snapshot_row in snapshot_rows:
        component_rows = conn.execute(
            "SELECT * FROM snapshot_components WHERE snapshot_id = ?",
            (snapshot_row["id"],),
        ).fetchall()
        components = tuple(
            ComponentValue(
                symbol=row["symbol"],
                quantity=row["quantity"],
                unit_price_usd=row["unit_price_usd"],
                value_usd=row["value_usd"],
                supply_quality=DataQuality(row["supply_quality"]),
                price_quality=DataQuality(row["price_quality"]),
                note=row["note"],
            )
            for row in component_rows
        )
        total = TotalValue(
            value_usd=snapshot_row["total_usd"],
            basis_note=snapshot_row["total_basis_note"],
            quality=DataQuality(snapshot_row["total_quality"]),
        )
        results.append(
            AssetClassResult(
                asset_class=snapshot_row["asset_class"],
                tokenized_usd=snapshot_row["tokenized_usd"],
                components=components,
                total=total,
                pct_tokenized=snapshot_row["pct_tokenized"],
                as_of=datetime.fromisoformat(snapshot_row["as_of_date"]),
                source_notes=snapshot_row["source_notes"],
            )
        )
    return results
