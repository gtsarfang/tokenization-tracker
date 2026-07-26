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
    st.set_page_config(page_title="Tokenization Tracker", page_icon="📊", layout="centered")
    st.title("Tokenization Tracker")
    st.caption("Tracking how much of each real-world asset class has moved on-chain.")

    config = load_config()
    conn = _get_connection(config.db_path)
    sources = registry.get_sources(config)

    viz.inject_base_css()

    if st.button("Refresh all"):
        for source in sources.values():
            refresh_asset_class(source, conn)

    for name, source in sources.items():
        result = fetch_latest_snapshot(conn, name)
        if result is None:
            result = refresh_asset_class(source, conn)

        if viz.render_asset_bar(result, key=name):
            refresh_asset_class(source, conn)
            st.rerun()


if __name__ == "__main__":
    main()
