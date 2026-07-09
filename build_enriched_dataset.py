import os
import pandas as pd

from scripts.tracking_dates import get_tracking_week_start

RAW_COLUMN_DTYPES = {
    "chart_date": "string",
    "current_position": "Int64",
    "title": "string",
    "artist_name": "string",
    "last_week_position": "string",
    "weeks_on_chart": "Int64",
    "awards_vector": "string",
}


def _quarter_label(month):
    if month <= 3:
        return "A"
    elif month <= 6:
        return "B"
    elif month <= 9:
        return "C"
    else:
        return "D"


def build_enriched_dataset(chart_name, raw_path=None, out_path=None):
    """
    Reads a chart's raw scraped CSV and produces the generic enriched
    dataset used for all filterable views: adds tracking_week_start-derived
    year/quarter/decade, a song_id join key, and debut/peak flags.
    """
    raw_path = raw_path or f"data/raw/{chart_name}.csv"
    out_path = out_path or f"data/processed/{chart_name}_enriched.parquet"

    df = pd.read_csv(raw_path, dtype=RAW_COLUMN_DTYPES)

    df["tracking_week_start"] = pd.to_datetime(
        df["chart_date"].apply(get_tracking_week_start)
    )

    df["year"] = df["tracking_week_start"].dt.year
    df["quarter"] = (
        df["year"].astype(str) + "-" +
        df["tracking_week_start"].dt.month.apply(_quarter_label)
    )
    df["decade"] = (df["year"] // 10 * 10).astype(str) + "s"

    df["song_id"] = df["title"].fillna("") + "|||" + df["artist_name"].fillna("")

    df["is_debut"] = df["last_week_position"] == "NEW"

    # Peak flag: sort chronologically per song, flag a row as a peak if its
    # position beats every prior appearance of that song. A song's first
    # chart appearance is always a peak by definition.
    df = df.sort_values(["song_id", "tracking_week_start", "chart_date"]).reset_index(drop=True)

    prior_best = df.groupby("song_id")["current_position"].transform(
        lambda s: s.shift(1).cummin()
    )
    df["is_peak"] = prior_best.isna() | (df["current_position"] < prior_best)

    df = df.sort_values(["tracking_week_start", "chart_date", "current_position"]).reset_index(drop=True)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    df.to_parquet(out_path, index=False)
    print(f"-> Saved enriched dataset with {len(df)} rows to {out_path}")

    return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--raw", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    build_enriched_dataset(args.chart, raw_path=args.raw, out_path=args.out)