"""
View B / Table 1: one row per RUN, combining run_total_points (raw) and
era_score, sortable/filterable by either raw points, era score, debut
(week, position), or peak (week, position). Rank-within-frame and
overall-rank columns are opt-in (computed only when requested).
"""
import pandas as pd
import streamlit as st

from lib.time_utils import sorted_desc, week_choices


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
        enriched[["song_id", "tracking_week_start", "current_position", "year", "quarter", "decade", "chart_date"]]
        .drop_duplicates(subset=["song_id", "tracking_week_start"])
    )

    base = base.merge(
        enriched_meta.rename(columns={
            "current_position": "debut_position", "year": "debut_year",
            "quarter": "debut_quarter", "decade": "debut_decade",
            "chart_date": "debut_chart_date",
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
    # peak_chart_date already exists on runs.parquet directly -- no need to refetch it.

    return base


def leaderboard_filters(base, key_prefix="lb"):
    """Renders the filter/sort widgets. Returns the filtered, sorted dataframe."""
    col1, col2, col3 = st.columns(3)

    with col1:
        frame_basis = st.radio(
            "Frame basis (for time + position filters)", ["Debut", "Peak"],
            key=f"{key_prefix}_basis", horizontal=True,
        )
    week_col = "run_start_week" if frame_basis == "Debut" else "peak_week"
    chart_date_col = "debut_chart_date" if frame_basis == "Debut" else "peak_chart_date"
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
            "Position filter",
            ["All positions", f"Exact {frame_basis.lower()} #k", f"{frame_basis} in Top N"],
            key=f"{key_prefix}_posmode",
        )

    mask = base.index == base.index
    if granularity == "Decade":
        options = sorted_desc(base[decade_col])
        value = st.selectbox("Decade", options, key=f"{key_prefix}_decade")
        mask &= base[decade_col] == value
    elif granularity == "Year":
        options = sorted_desc(base[year_col])
        value = st.selectbox("Year", options, key=f"{key_prefix}_year")
        mask &= base[year_col] == value
    elif granularity == "Quarter":
        options = sorted_desc(base[quarter_col])
        value = st.selectbox("Quarter", options, key=f"{key_prefix}_quarter")
        mask &= base[quarter_col] == value
    elif granularity == "Week":
        choices = week_choices(base, week_col, chart_date_col)
        idx = st.selectbox(
            "Week (chart date)", range(len(choices)), key=f"{key_prefix}_week",
            format_func=lambda i: choices[i][1],
        )
        mask &= base[week_col] == choices[idx][0]

    max_pos = int(base[pos_col].max())
    if pos_mode.startswith("Exact"):
        k = st.number_input("k", min_value=1, max_value=max_pos, value=1, key=f"{key_prefix}_k")
        mask &= base[pos_col] == k
    elif pos_mode.endswith("Top N"):
        n = st.number_input("N", min_value=1, max_value=max_pos, value=10, key=f"{key_prefix}_n")
        mask &= base[pos_col] <= n

    filtered = base[mask].copy()

    with st.expander("Rank filter: top-K per period (applied on top of the filters above)"):
        rf_enabled = st.checkbox("Enable", key=f"{key_prefix}_rf_on")
        rf1, rf2, rf3 = st.columns(3)
        with rf1:
            rf_granularity = st.selectbox("Group by", ["Decade", "Year", "Quarter"], key=f"{key_prefix}_rf_gran")
        with rf2:
            rf_metric_choice = st.selectbox("Metric", ["Raw points", "Era score"], key=f"{key_prefix}_rf_metric")
        with rf3:
            rf_mode = st.radio("Mode", ["Kth biggest", "Top N biggest"], key=f"{key_prefix}_rf_mode")
        rf_k = st.number_input(
            "k" if rf_mode == "Kth biggest" else "N", min_value=1,
            value=1 if rf_mode == "Kth biggest" else 5, key=f"{key_prefix}_rf_k",
        )
        st.caption(
            f"Groups by {frame_basis.lower()} {rf_granularity.lower()} (uses the frame basis "
            "chosen above) and keeps only each group's biggest song(s) by the chosen metric, "
            "computed over whatever's already passed the time/position filters above."
        )

    if rf_enabled:
        rf_group_col = {"Decade": decade_col, "Year": year_col, "Quarter": quarter_col}[rf_granularity]
        rf_metric_col = "run_total_points" if rf_metric_choice == "Raw points" else "era_score"
        filtered["period_rank"] = (
            filtered.groupby(rf_group_col)[rf_metric_col].rank(method="min", ascending=False)
        )
        if rf_mode == "Kth biggest":
            filtered = filtered[filtered["period_rank"] == rf_k]
        else:
            filtered = filtered[filtered["period_rank"] <= rf_k]
        filtered["period_rank"] = filtered["period_rank"].astype("Int64")

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