"""
View B / Table 1: one row per RUN, combining run_total_points (raw) and
era_score, sortable/filterable by either raw points, era score, debut
(week, position), or peak (week, position). Rank-within-frame and
overall-rank columns are opt-in (computed only when requested).
"""
import pandas as pd
import streamlit as st


def build_leaderboard_base(runs, era_scores, enriched):
    """
    One row per run. Debut week/position come from the run's own
    run_start_week joined against enriched (NOT from is_debut -- see
    the mismatch note: is_debut fires on any re-entry gap, including ones
    that don't start a new run, so it isn't a reliable 1:1 marker of
    "this row is where a run begins").
    """
    scores = era_scores[[
        "run_id", "era_score", "era_score_volume_adjusted", "is_finalized",
        "score_reason", "n_peers", "n_eff",
    ]]
    base = runs.merge(scores, on="run_id", how="left")

    enriched_meta = (
        enriched[["song_id", "tracking_week_start", "current_position", "year", "quarter", "decade"]]
        .drop_duplicates(subset=["song_id", "tracking_week_start"])
    )

    base = base.merge(
        enriched_meta.rename(columns={
            "current_position": "debut_position", "year": "debut_year",
            "quarter": "debut_quarter", "decade": "debut_decade",
        }),
        left_on=["song_id", "run_start_week"], right_on=["song_id", "tracking_week_start"],
        how="left",
    ).drop(columns=["tracking_week_start"])

    base = base.merge(
        enriched_meta[["song_id", "tracking_week_start", "year", "quarter", "decade"]].rename(
            columns={"year": "peak_year", "quarter": "peak_quarter", "decade": "peak_decade"}
        ),
        left_on=["song_id", "peak_week"], right_on=["song_id", "tracking_week_start"],
        how="left",
    ).drop(columns=["tracking_week_start"])

    return base


def leaderboard_filters(base, key_prefix="lb"):
    """Renders the filter/sort widgets. Returns (filtered_df, sort_col, ascending, frame_basis, rank_requested)."""
    col1, col2, col3 = st.columns(3)

    with col1:
        frame_basis = st.radio(
            "Frame basis (for time + position filters)", ["Debut", "Peak"],
            key=f"{key_prefix}_basis", horizontal=True,
        )
    week_col = "run_start_week" if frame_basis == "Debut" else "peak_week"
    year_col = f"{frame_basis.lower()}_year"
    quarter_col = f"{frame_basis.lower()}_quarter"
    decade_col = f"{frame_basis.lower()}_decade"
    pos_col = "debut_position" if frame_basis == "Debut" else "peak_position"

    with col2:
        granularity = st.selectbox(
            "Time frame", ["All time", "Decade", "Year", "Quarter", "Week"],
            key=f"{key_prefix}_gran",
        )
    with col3:
        pos_mode = st.radio(
            "Position filter", ["All positions", f"Exact {frame_basis.lower()} #k", "Top N"],
            key=f"{key_prefix}_posmode",
        )

    mask = base.index == base.index
    if granularity == "Decade":
        options = sorted(base[decade_col].dropna().unique())
        value = st.selectbox("Decade", options, key=f"{key_prefix}_decade")
        mask &= base[decade_col] == value
    elif granularity == "Year":
        options = sorted(base[year_col].dropna().unique())
        value = st.selectbox("Year", options, key=f"{key_prefix}_year")
        mask &= base[year_col] == value
    elif granularity == "Quarter":
        options = sorted(base[quarter_col].dropna().unique())
        value = st.selectbox("Quarter", options, key=f"{key_prefix}_quarter")
        mask &= base[quarter_col] == value
    elif granularity == "Week":
        options = sorted(base[week_col].dropna().unique())
        value = st.selectbox("Week", options, key=f"{key_prefix}_week", format_func=lambda d: str(d)[:10])
        mask &= base[week_col] == value

    max_pos = int(base[pos_col].max())
    if pos_mode.startswith("Exact"):
        k = st.number_input("k", min_value=1, max_value=max_pos, value=1, key=f"{key_prefix}_k")
        mask &= base[pos_col] == k
    elif pos_mode == "Top N":
        n = st.number_input("N", min_value=1, max_value=max_pos, value=10, key=f"{key_prefix}_n")
        mask &= base[pos_col] <= n

    filtered = base[mask].copy()

    sort_choice = st.selectbox(
        "Sort by",
        ["Raw points (run_total_points)", "Era score", "Debut (week, then position)", "Peak (week, then position)"],
        key=f"{key_prefix}_sort",
    )
    sort_map = {
        "Raw points (run_total_points)": (["run_total_points"], False),
        "Era score": (["era_score"], False),
        "Debut (week, then position)": (["run_start_week", "debut_position"], True),
        "Peak (week, then position)": (["peak_week", "peak_position"], True),
    }
    sort_cols, ascending = sort_map[sort_choice]
    filtered = filtered.sort_values(sort_cols, ascending=ascending)

    with st.expander("Rank columns (computed on request)"):
        show_ranks = st.checkbox("Show rank-within-frame and overall rank", key=f"{key_prefix}_showrank")
        rank_basis = st.radio("Rank by", ["Raw points", "Era score"], key=f"{key_prefix}_rankbasis", horizontal=True)

    if show_ranks:
        metric_col = "run_total_points" if rank_basis == "Raw points" else "era_score"
        period_col = {
            "All time": None, "Decade": decade_col, "Year": year_col,
            "Quarter": quarter_col, "Week": week_col,
        }[granularity]
        filtered["rank_overall"] = base[metric_col].rank(method="min", ascending=False).reindex(filtered.index).astype("Int64")
        if period_col:
            filtered["rank_within_frame"] = (
                base.groupby(period_col)[metric_col]
                .rank(method="min", ascending=False)
                .reindex(filtered.index).astype("Int64")
            )

    return filtered