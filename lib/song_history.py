"""
Interactive per-song chart-run visualization, shared across every tab so it
always shows the same thing regardless of where it was triggered from.

X-axis is a synthetic sequential position per actual chart appearance, NOT
real calendar time -- any stretch where the song wasn't charting at all
(whether a small within-run gap or a multi-year gap between separate runs)
collapses to a small fixed step instead of "spending space" proportional to
how long it really was. Real dates are preserved via hover (every point) and
via sparse tick labels (start/end of each run only, to avoid clutter).

Y-axis is chart position, inverted so #1 sits at top. In linear mode the
top tick is forced to be exactly 1, with regular steps below it. In log
mode, Plotly's natural log ticks (powers of 10) already put 1 at the top on
their own, so those are left as default rather than overridden.
"""
import math
import plotly.graph_objects as go
import streamlit as st

from build_chart_runs import GAP_WEEKS

SEGMENT_GAP_SLOTS = 3  # visual "jump" width between separate runs, in plot-x units


def segment_song_history(song_df):
    """Adds a 'segment' column: increments every time the gap since the
    previous chart appearance exceeds GAP_WEEKS, same rule as build_chart_runs.py."""
    song_df = song_df.sort_values("tracking_week_start").reset_index(drop=True).copy()
    gap_days = song_df["tracking_week_start"].diff().dt.days
    new_segment = gap_days.isna() | (gap_days > GAP_WEEKS * 7)
    song_df["segment"] = new_segment.cumsum()
    return song_df


def _assign_plot_x(song_df):
    """Sequential integer x-position per row. Any real elapsed time where the
    song wasn't charting -- within a run or between separate runs -- collapses
    to the same fixed small step, so the axis only spends space on weeks the
    song actually charted."""
    xs = []
    cursor = 0
    prev_segment = None
    for _, row in song_df.iterrows():
        if prev_segment is not None and row["segment"] != prev_segment:
            cursor += SEGMENT_GAP_SLOTS
        xs.append(cursor)
        cursor += 1
        prev_segment = row["segment"]
    song_df = song_df.copy()
    song_df["plot_x"] = xs
    return song_df


def _nice_step(max_val, target_ticks=6):
    """A conventional 1/2/5-times-a-power-of-ten step size, chosen so the
    axis ends up with roughly target_ticks gridlines -- the standard "nice
    numbers" approach most charting libraries use for default tick spacing."""
    if max_val <= 1:
        return 1
    raw_step = max_val / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw_step))
    for m in (1, 2, 5, 10):
        step = m * magnitude
        if step >= raw_step:
            return int(step)
    return int(magnitude * 10)


def build_song_history_figure(song_df, title, log_scale=False):
    song_df = segment_song_history(song_df)
    song_df = _assign_plot_x(song_df)

    fig = go.Figure()
    tickvals, ticktext = [], []
    for _, seg in song_df.groupby("segment"):
        fig.add_trace(go.Scatter(
            x=seg["plot_x"], y=seg["current_position"],
            mode="lines+markers",
            line=dict(color="steelblue"),
            marker=dict(size=6),
            showlegend=False,
            customdata=seg["chart_date"],
            hovertemplate="Chart date: %{customdata}<br>Position: %{y}<extra></extra>",
        ))
        # Label just the start/end of each run for orientation; hover covers
        # exact dates for everything in between.
        tickvals += [int(seg["plot_x"].iloc[0]), int(seg["plot_x"].iloc[-1])]
        ticktext += [str(seg["chart_date"].iloc[0]), str(seg["chart_date"].iloc[-1])]

    fig.update_xaxes(title="Chart date (published)", tickvals=tickvals, ticktext=ticktext, tickangle=45)

    max_pos = int(song_df["current_position"].max())
    if log_scale:
        log_max = math.log10(max_pos)
        log_span = max(log_max, 0.1)  # avoid a degenerate zero span if max_pos == 1
        log_pad = log_span * 0.08
        fig.update_yaxes(
            type="log",
            # top pads slightly past log10(1)=0 so a marker AT position 1 isn't
            # clipped by the plot edge; tick 1 itself still reads as the top.
            range=[log_max + log_pad, -log_pad],
            zeroline=False,
            title="Chart position (log scale)",
        )
    else:
        step = _nice_step(max_pos)
        ticks = sorted(set([1] + list(range(step, max_pos + step, step))))
        span = max(max_pos - 1, 1)  # avoid a degenerate zero span if max_pos == 1
        pad = span * 0.05
        fig.update_yaxes(
            # Same reasoning as the log branch: range pads slightly past 1 for
            # marker headroom, but tickvals below still stop exactly at 1.
            range=[max_pos + pad, 1 - pad],
            zeroline=False,
            title="Chart position",
            tickvals=ticks,
        )

    fig.update_layout(title=title, height=600, hovermode="closest")
    return fig


def render_song_history_section(candidates_df, enriched, chart_name, key_prefix):
    """
    Shared UI block: song picker + log-scale toggle + generate button + plot.
    Called identically from every tab (with that tab's own filtered results
    as the candidate list) so the visualization behaves the same everywhere.
    The active selection is intentionally keyed by chart_name only (not
    key_prefix), so picking a song's plot in one tab keeps showing it if you
    switch to another tab, rather than resetting per tab.
    """
    st.subheader("Song chart run")
    song_options = candidates_df[["song_id", "title", "artist_name"]].drop_duplicates().head(200)
    song_labels = song_options["title"] + " -- " + song_options["artist_name"]
    song_choice = st.selectbox(
        "Pick a song to visualize (from the filtered table above, first 200 shown)",
        song_options.index,
        format_func=lambda i: song_labels.loc[i] if i in song_labels.index else str(i),
        key=f"{key_prefix}_song_viz_choice",
    )
    log_scale = st.checkbox("Log scale (y-axis)", key=f"{key_prefix}_song_viz_log")

    if st.button("Show chart run", key=f"{key_prefix}_song_viz_button") and song_choice is not None:
        st.session_state[f"song_viz_id::{chart_name}"] = song_options.loc[song_choice, "song_id"]

    active_song_id = st.session_state.get(f"song_viz_id::{chart_name}")
    if active_song_id is not None:
        try:
            song_df = enriched[enriched["song_id"] == active_song_id]
            title = f"{song_df['title'].iloc[0]} -- {song_df['artist_name'].iloc[0]}"
            fig = build_song_history_figure(song_df, title, log_scale=log_scale)
            st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_song_viz_chart")
        except Exception as e:
            st.warning(f"Couldn't build a chart-run plot for this song ({e.__class__.__name__}: {e}).")