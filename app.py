import os
import streamlit as st

from lib.data import (
    discover_charts, get_enriched, get_runs, get_era_scores, _mtime,
)
from lib.filters import raw_explorer_filters
from lib.leaderboard import build_leaderboard_base, leaderboard_filters
from lib.frame_view import frame_standings_widget
from lib.diagnostic import get_era_fit_figure

st.set_page_config(page_title="Billboard Chart Explorer", layout="wide")
st.title("Billboard Chart Explorer")

charts = discover_charts()
if not charts:
    st.error(
        "No chart data found under data/processed/ (expected files like "
        "hot-100_enriched.parquet). Run the pipeline first."
    )
    st.stop()

chart_name = st.sidebar.selectbox(
    "Chart", list(charts.keys()),
    format_func=lambda name: charts[name]["display_name"],
)
chart = charts[chart_name]
enriched = get_enriched(chart)

tab_labels = ["Raw Data Explorer"]
if chart["has_scoring"]:
    tab_labels += ["All-Time Leaderboard", "Frame Standings"]
tabs = st.tabs(tab_labels)

with tabs[0]:
    st.caption(
        "One row per position-in-a-week. 'Debuts' here means any real "
        "re-entry after a gap (matches the raw is_debut flag) -- a song "
        "can have several across its history, which is a different count "
        "than the number of scored runs in the Leaderboard tab."
    )
    filtered = raw_explorer_filters(enriched)
    st.write(f"{len(filtered):,} rows")
    st.dataframe(filtered, use_container_width=True, height=500)

if chart["has_scoring"]:
    runs = get_runs(chart)
    era_scores = get_era_scores(chart)
    base = build_leaderboard_base(runs, era_scores, enriched)

    with tabs[1]:
        st.caption(
            "One row per scored run. era_score_volume_adjusted is available "
            "in the underlying data but omitted here per your preference -- "
            "let me know if you'd like it added as a toggle."
        )
        lb_filtered = leaderboard_filters(base)
        st.write(f"{len(lb_filtered):,} runs")
        display_cols = [
            "title", "artist_name", "run_total_points", "era_score",
            "run_start_week", "debut_position", "peak_week", "peak_position",
            "is_finalized", "n_peers",
        ]
        display_cols += [c for c in ("rank_within_frame", "rank_overall") if c in lb_filtered.columns]
        st.dataframe(lb_filtered[display_cols], use_container_width=True, height=400)

        st.subheader("Diagnostic drill-down")
        options = lb_filtered.head(200)  # cap the picker to a sane size
        labels = (
            options["title"] + " -- " + options["artist_name"]
            + " (" + options["peak_week"].astype(str).str.slice(0, 10) + ")"
        )
        choice = st.selectbox(
            "Pick a run to inspect (from the filtered table above, first 200 shown)",
            options.index, format_func=lambda i: labels.loc[i] if i in labels.index else str(i),
        )
        if choice is not None:
            run_id = options.loc[choice, "run_id"]
            fig, result = get_era_fit_figure(
                chart_name, run_id, _mtime(chart["paths"]["runs"]),
            )
            st.pyplot(fig)
            st.json({k: v for k, v in result.items() if k != "score" or True})

    with tabs[2]:
        st.caption(
            "Points truncated at the frame boundary (year-end-chart style), "
            "not whole runs that merely peaked inside the frame. No era "
            "score here -- that adjustment doesn't have a clean meaning "
            "once a run is arbitrarily cut off mid-way."
        )
        standings = frame_standings_widget(enriched, chart_name, _mtime(chart["paths"]["enriched"]))
        st.write(f"{len(standings):,} songs")
        st.dataframe(standings, use_container_width=True, height=500)