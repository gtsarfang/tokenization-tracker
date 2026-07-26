"""Tokenization Tracker — Streamlit app.

Thin wiring only: config -> registry -> orchestrator -> viz. No business logic here.
"""

from __future__ import annotations

import sqlite3

import streamlit as st

from config import load_config
from reality_check import registry, viz
from reality_check.orchestrator import refresh_asset_class
from reality_check.storage import fetch_latest_snapshot, get_connection, init_db


@st.cache_resource
def _get_connection(db_path: str) -> sqlite3.Connection:
    conn = get_connection(db_path)
    init_db(conn)
    return conn


def main() -> None:
    st.set_page_config(page_title="Tokenization Tracker", page_icon="📊", layout="wide")

    config = load_config()
    conn = _get_connection(config.db_path)
    sources = registry.get_sources(config)

    viz.inject_base_css()
    viz.render_header(
        "Tokenization Tracker",
        "Tracking how much of each real-world asset class has moved on-chain.",
    )

    if st.button("Refresh all"):
        for source in sources.values():
            refresh_asset_class(source, conn)

    results = {}
    for name, source in sources.items():
        result = fetch_latest_snapshot(conn, name)
        if result is None:
            result = refresh_asset_class(source, conn)
        results[name] = result

    # Pad every card's breakdown to the same number of rows so cards line up to
    # the same height regardless of how many components an asset class has.
    max_components = max(len(result.components) for result in results.values())

    names = list(sources.keys())
    cards_per_row = 3
    for row_start in range(0, len(names), cards_per_row):
        row_names = names[row_start : row_start + cards_per_row]
        columns = st.columns(cards_per_row)
        for column, name in zip(columns, row_names):
            with column:
                source = sources[name]
                result = results[name]

                if viz.render_asset_bar(
                    result,
                    key=name,
                    methodology=source.describe_methodology(),
                    quantity=source.describe_quantity(result),
                    pad_rows_to=max_components,
                ):
                    refresh_asset_class(source, conn)
                    st.rerun()


if __name__ == "__main__":
    main()
