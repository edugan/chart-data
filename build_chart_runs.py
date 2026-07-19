import argparse
import os
import pandas as pd

from scripts.scoring import SCORING_FUNCTIONS

GAP_WEEKS = 26  # a run ends and a new one begins after this many weeks absent


def build_chart_runs(chart_name, enriched_path=None, out_path=None):
    """
    Segments each song's chart history into distinct "runs" -- a run ends
    and a new one begins whenever there's a gap of more than GAP_WEEKS
    between consecutive chart appearances (e.g. a holiday song's yearly
    returns, or a genuine resurgence, are each their own run).

    For each run, computes: peak week/position (first week the run's best
    position was reached), total points earned within that run only, the
    run's start/end tracking week, and whether the run is still "active"
    (its most recent appearance is in the single latest chart week
    currently in the data -- meaning the song is charting right now, and
    this run isn't over yet).
    """
    if chart_name not in SCORING_FUNCTIONS:
        raise ValueError(
            f"No scoring formula defined for chart '{chart_name}'. "
            f"Available: {list(SCORING_FUNCTIONS.keys())}"
        )
    scoring_fn = SCORING_FUNCTIONS[chart_name]

    enriched_path = enriched_path or f"data/processed/{chart_name}_enriched.parquet"
    out_path = out_path or f"data/processed/{chart_name}_runs.parquet"

    df = pd.read_parquet(enriched_path)
    df["points"] = scoring_fn(df["current_position"])

    df = df.sort_values(["song_id", "tracking_week_start", "chart_date"]).reset_index(drop=True)

    # Flag the start of a new run: either the song's first-ever appearance,
    # or a gap of more than GAP_WEEKS since its previous appearance.
    prev_week = df.groupby("song_id")["tracking_week_start"].shift(1)
    gap_days = (df["tracking_week_start"] - prev_week).dt.days
    new_run_flag = prev_week.isna() | (gap_days > GAP_WEEKS * 7)

    df["run_number"] = new_run_flag.groupby(df["song_id"]).cumsum()
    df["run_id"] = df["song_id"] + "::" + df["run_number"].astype(str)

    latest_week = df["tracking_week_start"].max()

    run_groups = df.groupby("run_id")

    run_info = run_groups.agg(
        song_id=("song_id", "first"),
        title=("title", "first"),
        artist_name=("artist_name", "first"),
        run_total_points=("points", "sum"),
        run_start_week=("tracking_week_start", "min"),
        run_end_week=("tracking_week_start", "max"),
    )

    # Peak: the first row (chronologically within the run) achieving the
    # run's best (lowest) position
    min_pos_per_run = run_groups["current_position"].transform("min")
    peak_rows = (
        df[df["current_position"] == min_pos_per_run]
        .sort_values(["run_id", "tracking_week_start"])
        .drop_duplicates("run_id", keep="first")
    )
    peak_info = peak_rows.set_index("run_id")[["tracking_week_start", "current_position", "chart_date"]]
    peak_info.columns = ["peak_week", "peak_position", "peak_chart_date"]

    result = run_info.join(peak_info).reset_index()
    result["is_active"] = result["run_end_week"] == latest_week

    result = result.sort_values("peak_week").reset_index(drop=True)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    result.to_parquet(out_path, index=False)
    print(f"-> Saved {len(result)} runs to {out_path}")
    # print(f"   Active runs (currently charting): {result['is_active'].sum()}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--enriched", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    build_chart_runs(args.chart, enriched_path=args.enriched, out_path=args.out)