"""Streamlit drift dashboard.

Run with:
    streamlit run dashboard/app.py -- --db runs.duckdb
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.duckdb_store import connect, find_regressions, load_divergences  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("runs.duckdb"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    st.set_page_config(page_title="AgentEvalHub — Drift Dashboard", layout="wide")
    st.title("AgentEvalHub — Drift Dashboard")

    if not args.db.exists():
        st.warning(f"No database at {args.db}. Run an eval with `--db {args.db}` first.")
        return

    con = connect(args.db)

    runs = con.execute("SELECT * FROM runs ORDER BY ts ASC").fetchdf()
    if runs.empty:
        st.info("Database is empty. Run at least one eval.")
        return

    suites = sorted(runs["suite"].unique())
    providers = sorted(runs["provider"].unique())

    col1, col2 = st.columns(2)
    suite = col1.selectbox("Suite", suites)
    provider = col2.selectbox("Provider", providers)

    filtered = runs[(runs["suite"] == suite) & (runs["provider"] == provider)].copy()
    if filtered.empty:
        st.info("No runs for that suite+provider combination yet.")
        return

    st.subheader("Pass rate over time")
    chart_df = filtered.set_index("ts")[["pass_rate"]]
    st.line_chart(chart_df)

    st.subheader("Token usage over time")
    token_df = filtered.set_index("ts")[["input_tokens", "output_tokens"]]
    st.line_chart(token_df)

    st.subheader("Latest regressions (passed last run, failed this run)")
    regressions = find_regressions(con, suite, provider)
    if regressions:
        st.error(f"{len(regressions)} regression(s) detected")
        st.dataframe(pd.DataFrame(regressions))
    else:
        st.success("No regressions vs previous run")

    st.subheader("Recent runs")
    st.dataframe(filtered.sort_values("ts", ascending=False).head(20))

    st.subheader("Cross-surface divergences")
    st.caption("Tasks where two surfaces (e.g. cloud vs. device) gave disagreeing answers. "
               "Populated by `python -m runner.run_cross_surface --db <db>`.")
    divergences = load_divergences(con, suite=suite, limit=50)
    if divergences:
        st.warning(f"{len(divergences)} divergence(s) logged for suite={suite}")
        st.dataframe(pd.DataFrame(divergences))
    else:
        st.info("No cross-surface divergences logged for this suite.")


if __name__ == "__main__":
    main()
