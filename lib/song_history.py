"""
Interactive per-song chart-run visualization for the Raw Data Explorer tab.
X-axis is the published chart_date (not tracking_week_start -- consistent
with the rest of the dashboard preferring the date people actually
recognize). Y-axis is chart position, inverted so #1 sits at the top.

A song's full history is split into separate plot traces at the same
>GAP_WEEKS boundary build_chart_runs.py uses to split runs, so a visual
"jump" here always means the same thing as a separate row in the
Leaderboard tab. Reusing GAP_WEEKS works even for charts with no
era-scoring at all -- the run-boundary rule itself never touches points or
SCORING_FUNCTIONS, only the rest of that module's setup does.
"""
import pandas as pd
import plotly.graph_objects as go

from build_chart_runs import GAP_WEEKS


def segment_song_history(song_df):
    """Adds a 'segment' column: increments every time the gap since the
    previous chart appearance exceeds GAP_WEEKS, same rule as build_chart_runs.py."""
    song_df = song_df.sort_values("tracking_week_start").reset_index(drop=True).copy()
    gap_days = song_df["tracking_week_start"].diff().dt.days
    new_segment = gap_days.isna() | (gap_days > GAP_WEEKS * 7)
    song_df["segment"] = new_segment.cumsum()
    return song_df


def build_song_history_figure(song_df, title):
    song_df = segment_song_history(song_df)
    song_df["chart_date_dt"] = pd.to_datetime(song_df["chart_date"])

    fig = go.Figure()
    for _, seg in song_df.groupby("segment"):
        fig.add_trace(go.Scatter(
            x=seg["chart_date_dt"], y=seg["current_position"],
            mode="lines+markers",
            line=dict(color="steelblue"),
            marker=dict(size=6),
            showlegend=False,
            hovertemplate="Chart date: %{x|%Y-%m-%d}<br>Position: %{y}<extra></extra>",
        ))

    fig.update_yaxes(autorange="reversed", title="Chart position")
    fig.update_xaxes(title="Chart date (published)")
    fig.update_layout(title=title, height=450, hovermode="closest")
    return fig