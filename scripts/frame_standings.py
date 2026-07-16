import pandas as pd


def compute_frame_standings(df_with_points, start_date, end_date):
    """
    Given an enriched dataframe with a 'points' column, sums each song/
    album's points within [start_date, end_date] (inclusive, based on
    tracking_week_start), cutting off any part of a run outside that
    window. Also computes rank and how many points were gained in the most
    recent chart week within the frame, so movement can be shown.

    "Most recent chart week" means the latest tracking_week_start actually
    present in the data within the frame -- not a fixed day offset -- since
    chart weeks aren't always exactly 7 days apart (see the 2015-07-25 case).
    """
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    frame = df_with_points[
        (df_with_points["tracking_week_start"] >= start)
        & (df_with_points["tracking_week_start"] <= end)
    ]

    empty_cols = ["song_id", "title", "artist_name", "points_total",
                  "points_prior", "points_added_last_week",
                  "rank_current", "rank_previous"]
    if frame.empty:
        return pd.DataFrame(columns=empty_cols)

    last_week = frame["tracking_week_start"].max()

    total = frame.groupby("song_id")["points"].sum().rename("points_total")

    prior_frame = frame[frame["tracking_week_start"] < last_week]
    prior = prior_frame.groupby("song_id")["points"].sum().rename("points_prior")

    rep = frame.sort_values("tracking_week_start").groupby("song_id").first()[["title", "artist_name"]]

    result = total.to_frame().join(prior).join(rep)
    result["points_prior"] = result["points_prior"].fillna(0.0)
    result["points_added_last_week"] = result["points_total"] - result["points_prior"]

    result["rank_current"] = result["points_total"].rank(method="min", ascending=False).astype(int)

    # Previous-week rank: only computed among songs/albums that actually had
    # prior points, so brand-new-this-week entries don't distort the prior ordering.
    had_prior = result[result["points_prior"] > 0]
    prev_rank = had_prior["points_prior"].rank(method="min", ascending=False)
    result["rank_previous"] = prev_rank.reindex(result.index)  # NaN if no prior points

    result = result.reset_index().sort_values("rank_current")
    return result[empty_cols]