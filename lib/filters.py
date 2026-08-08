"""
Filter widgets + filtering logic for View A (raw dataset explorer).
Time-frame choices are read off the data itself (not a generated calendar),
since chart weeks aren't always exactly 7 days apart.
"""
import streamlit as st

from lib.time_utils import sorted_desc, week_choices


def time_frame_widget(df, key_prefix, week_col="tracking_week_start",
                       year_col="year", quarter_col="quarter", decade_col="decade",
                       chart_date_col="chart_date"):
    """Renders granularity + value selectors. Returns a boolean mask (all True if 'All time')."""
    granularity = st.selectbox(
        "Time frame", ["All time", "Decade", "Year", "Quarter", "Week"],
        key=f"{key_prefix}_gran",
    )

    if granularity == "All time":
        return df.index == df.index  # all True, same length/index as df

    if granularity == "Decade":
        options = sorted_desc(df[decade_col])
        value = st.selectbox("Decade", options, key=f"{key_prefix}_decade")
        return df[decade_col] == value

    if granularity == "Year":
        options = sorted_desc(df[year_col])
        value = st.selectbox("Year", options, key=f"{key_prefix}_year")
        return df[year_col] == value

    if granularity == "Quarter":
        options = sorted_desc(df[quarter_col])
        value = st.selectbox("Quarter", options, key=f"{key_prefix}_quarter")
        return df[quarter_col] == value

    # Week -- label shows the published chart date, filtering still keys off
    # week_col (tracking_week_start), since that's the internal anchor used
    # for joins elsewhere.
    choices = week_choices(df, week_col, chart_date_col)
    idx = st.selectbox(
        "Week (chart date)", range(len(choices)), key=f"{key_prefix}_week",
        format_func=lambda i: choices[i][1],
    )
    return df[week_col] == choices[idx][0]


def position_widget(df, key_prefix, position_col="current_position"):
    """Renders position-filter mode + value. Returns a boolean mask."""
    mode = st.radio(
        "Position filter", ["All positions", "Exact position (#k)", "Top N"],
        key=f"{key_prefix}_posmode", horizontal=True,
    )
    if mode == "All positions":
        return df.index == df.index

    max_pos = int(df[position_col].max())
    if mode == "Exact position (#k)":
        k = st.number_input("k", min_value=1, max_value=max_pos, value=1, key=f"{key_prefix}_k")
        return df[position_col] == k

    n = st.number_input("N", min_value=1, max_value=max_pos, value=10, key=f"{key_prefix}_n")
    return df[position_col] <= n


def restriction_widget(key_prefix):
    """Renders the all/debuts-only/peaks-only radio. Returns the chosen label."""
    return st.radio(
        "Restrict to", ["All rows", "Debuts only", "Peaks only"],
        key=f"{key_prefix}_restrict", horizontal=True,
    )


def apply_restriction(df, restriction, debut_col="is_debut", peak_col="is_peak"):
    if restriction == "Debuts only":
        return df[df[debut_col].fillna(False)]
    if restriction == "Peaks only":
        return df[df[peak_col].fillna(False)]
    return df


def raw_explorer_filters(df, key_prefix="rawexp"):
    """
    Full View A filter pipeline: time frame + position + restriction, applied
    in that order (restriction last, since 'debuts/peaks within top N in Q3
    1990' composes all three).
    Returns the filtered, sorted dataframe.
    """
    col1, col2 = st.columns(2)
    with col1:
        time_mask = time_frame_widget(df, key_prefix)
    with col2:
        pos_mask = position_widget(df, key_prefix)

    restriction = restriction_widget(key_prefix)

    filtered = df[time_mask & pos_mask]
    filtered = apply_restriction(filtered, restriction)

    sort_cols = [c for c in ["tracking_week_start", "current_position"] if c in filtered.columns]
    if sort_cols:
        filtered = filtered.sort_values(sort_cols)

    return filtered