"""
View B / Table 2: frame-restricted standings. Points are truncated at the
frame boundary (a song's run gets cut off, not excluded/included whole),
using scripts.frame_standings.compute_frame_standings. No era_score here
by design -- that adjustment doesn't have a clean meaning once the run
itself is arbitrarily truncated.
"""
import streamlit as st
import pandas as pd

from scripts.scoring import SCORING_FUNCTIONS
from scripts.frame_standings import compute_frame_standings
from lib.time_utils import sorted_desc, week_choices


@st.cache_data(show_spinner="Computing points for every chart row...")
def annotate_points(enriched, chart_name, _mtime_key=None):
    """Adds a 'points' column via the chart's fitted scoring formula. Cached
    since this touches every row and chart_name/points are static given the
    chart's params -- only recomputed if the underlying enriched file changes."""
    fn = SCORING_FUNCTIONS[chart_name]
    df = enriched.copy()
    df["points"] = fn(df["current_position"].astype(float))
    return df


def frame_standings_widget(enriched, chart_name, mtime_key, key_prefix="frame"):
    df_with_points = annotate_points(enriched, chart_name, mtime_key)

    granularity = st.selectbox(
        "Frame", ["Decade", "Year", "Quarter", "Custom range"], key=f"{key_prefix}_gran",
    )

    if granularity == "Decade":
        options = sorted_desc(df_with_points["decade"])
        value = st.selectbox("Decade", options, key=f"{key_prefix}_decade")
        sub = df_with_points[df_with_points["decade"] == value]
    elif granularity == "Year":
        options = sorted_desc(df_with_points["year"])
        value = st.selectbox("Year", options, key=f"{key_prefix}_year")
        sub = df_with_points[df_with_points["year"] == value]
    elif granularity == "Quarter":
        options = sorted_desc(df_with_points["quarter"])
        value = st.selectbox("Quarter", options, key=f"{key_prefix}_quarter")
        sub = df_with_points[df_with_points["quarter"] == value]
    else:
        # Labels show the published chart date; the underlying value used
        # for filtering is still tracking_week_start. Choices come back
        # most-recent-first, so index 0 = most recent, index -1 = earliest.
        choices = week_choices(df_with_points, "tracking_week_start", "chart_date")
        c1, c2 = st.columns(2)
        with c1:
            start_idx = st.selectbox(
                "Start week (chart date)", range(len(choices)), index=len(choices) - 1,
                key=f"{key_prefix}_start", format_func=lambda i: choices[i][1],
            )
        with c2:
            end_idx = st.selectbox(
                "End week (chart date)", range(len(choices)), index=0,
                key=f"{key_prefix}_end", format_func=lambda i: choices[i][1],
            )
        start, end = choices[start_idx][0], choices[end_idx][0]

    if granularity == "Custom range":
        start_date, end_date = start, end
    else:
        start_date, end_date = sub["tracking_week_start"].min(), sub["tracking_week_start"].max()

    standings = compute_frame_standings(df_with_points, start_date, end_date)

    standings = standings.rename(columns={
        "points_total": "points_in_frame",
        "points_added_last_week": "points_added_last_chart_week",
    })
    standings["movement"] = standings["rank_previous"] - standings["rank_current"]

    return standings