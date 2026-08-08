"""Shared helpers for time-based dropdown widgets, used across filters.py,
leaderboard.py, and frame_view.py."""
import pandas as pd


def sorted_desc(values):
    """Unique, non-null values sorted most-recent/largest first."""
    vals = pd.Series(values).dropna().unique()
    return sorted(vals, reverse=True)


def week_choices(df, week_col, chart_date_col):
    """
    Returns [(week_value, chart_date_label), ...] deduplicated on week_col,
    sorted most-recent-first by week_col.

    week_col is whatever's actually used for filtering/joins elsewhere
    (tracking_week_start, run_start_week, peak_week -- an internal,
    not-necessarily-user-facing anchor date). chart_date_col is the
    Billboard-published date, which is what should actually be shown in
    the dropdown label.
    """
    sub = (
        df[[week_col, chart_date_col]]
        .dropna(subset=[week_col])
        .drop_duplicates(subset=[week_col])
        .sort_values(week_col, ascending=False)
    )
    return list(sub.itertuples(index=False, name=None))