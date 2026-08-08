"""
Display-only cleanup, applied right before st.dataframe calls. Never mutates
the data used upstream for filtering/sorting/joins -- always operates on a
copy, right at the point of rendering.
"""

DROP_COLS = ("song_id",)


def clean_for_display(df, date_cols=()):
    out = df.drop(columns=[c for c in DROP_COLS if c in df.columns], errors="ignore").copy()
    for c in date_cols:
        if c in out.columns:
            out[c] = out[c].dt.date  # drops the 00:00:00 time-of-day
    return out