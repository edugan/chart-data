import argparse
import os
import pandas as pd

from scripts.scoring import SCORING_FUNCTIONS

DEBUT_INFO_COLUMNS = ["chart_date", "tracking_week_start", "current_position", "year", "quarter", "decade"]
DEBUT_RENAME = {
    "chart_date": "debut_chart_date",
    "tracking_week_start": "debut_tracking_week_start",
    "current_position": "debut_position",
    "year": "debut_year",
    "quarter": "debut_quarter",
    "decade": "debut_decade",
}
PEAK_RENAME = {
    "chart_date": "peak_chart_date",
    "tracking_week_start": "peak_tracking_week_start",
    "current_position": "peak_position",
    "year": "peak_year",
    "quarter": "peak_quarter",
    "decade": "peak_decade",
}


def build_chart_totals(chart_name, enriched_path=None, out_path=None):
    """
    Builds the all-time totals table for a point-scored chart (works for
    song charts like the Hot 100 or album charts like the Billboard 200):
    one row per song/album with its total points across its whole run, plus
    debut and peak week/position (and their year/quarter/decade) for
    sorting/filtering.
    """
    if chart_name not in SCORING_FUNCTIONS:
        raise ValueError(
            f"No scoring formula defined for chart '{chart_name}'. "
            f"Available: {list(SCORING_FUNCTIONS.keys())}"
        )
    scoring_fn = SCORING_FUNCTIONS[chart_name]

    enriched_path = enriched_path or f"data/processed/{chart_name}_enriched.parquet"
    out_path = out_path or f"data/processed/{chart_name}_chart_totals.parquet"

    df = pd.read_parquet(enriched_path)
    df["points"] = scoring_fn(df["current_position"])

    df = df.sort_values(["song_id", "tracking_week_start", "chart_date"]).reset_index(drop=True)

    totals = df.groupby("song_id")["points"].sum().rename("total_points")

    rep = df.groupby("song_id").first()[["title", "artist_name"]]

    debut_rows = df[df["is_debut"]].drop_duplicates("song_id", keep="first")
    debut_info = debut_rows.set_index("song_id")[DEBUT_INFO_COLUMNS].rename(columns=DEBUT_RENAME)

    min_pos = df.groupby("song_id")["current_position"].transform("min")
    peak_rows = df[df["is_peak"] & (df["current_position"] == min_pos)].drop_duplicates("song_id", keep="first")
    peak_info = peak_rows.set_index("song_id")[DEBUT_INFO_COLUMNS].rename(columns=PEAK_RENAME)

    result = (
        totals.to_frame()
        .join(rep)
        .join(debut_info)
        .join(peak_info)
        .reset_index()
    )

    cols = [
        "song_id", "title", "artist_name", "total_points",
        "debut_chart_date", "debut_tracking_week_start", "debut_position",
        "debut_year", "debut_quarter", "debut_decade",
        "peak_chart_date", "peak_tracking_week_start", "peak_position",
        "peak_year", "peak_quarter", "peak_decade",
    ]
    result = result[cols].sort_values("total_points", ascending=False).reset_index(drop=True)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    result.to_parquet(out_path, index=False)
    print(f"-> Saved chart totals with {len(result)} rows to {out_path}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--enriched", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    build_chart_totals(args.chart, enriched_path=args.enriched, out_path=args.out)