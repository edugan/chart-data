import argparse
import pandas as pd

from build_enriched_dataset import RAW_COLUMN_DTYPES
from scripts.utils import generate_chart_dates


def check_new_chart(chart_name, raw_path=None):
    """
    Generic first-pass QA for a freshly scraped chart's raw data, before it
    gets trusted enough to build the enriched dataset on top of. Checks for
    missing weeks, entry-count changes, duplicates within a week, and
    weeks_on_chart/NEW-flag inconsistencies.
    """
    raw_path = raw_path or f"data/raw/{chart_name}.csv"
    df = pd.read_csv(raw_path, dtype=RAW_COLUMN_DTYPES)

    print("=" * 60)
    print(f"CHECKING NEW CHART: {chart_name}")
    print("=" * 60)
    print(f"\nTotal rows: {len(df)}")
    print(f"Date range: {df['chart_date'].min()} to {df['chart_date'].max()}")

    expected = set(generate_chart_dates(df["chart_date"].min(), df["chart_date"].max()))
    have = set(df["chart_date"].unique())
    missing_weeks = sorted(expected - have)
    print(f"\n[1] Missing weeks: {len(missing_weeks)}")
    if missing_weeks:
        print(missing_weeks)

    per_week = df.groupby("chart_date").size().sort_index()
    prev_count = per_week.shift(1)
    changed = per_week[(per_week != prev_count) & prev_count.notna()]
    print(f"\n[2] Weeks with entry count different from the prior week: {len(changed)}")
    if len(changed) > 0:
        comparison = pd.DataFrame({"count": per_week, "prev_week_count": prev_count})
        print(comparison.loc[changed.index])

    df["song_id"] = df["title"].fillna("") + "|||" + df["artist_name"].fillna("")

    dup_song = df[df.duplicated(subset=["chart_date", "song_id"], keep=False)]
    print(f"\n[3] Duplicate (chart_date, song_id) rows: {len(dup_song)}")
    if len(dup_song) > 0:
        print(dup_song.sort_values(["chart_date", "song_id"])[["chart_date", "title", "artist_name", "current_position"]])

    dup_pos = df[df.duplicated(subset=["chart_date", "current_position"], keep=False)]
    print(f"\n[4] Duplicate (chart_date, current_position) rows: {len(dup_pos)}")
    if len(dup_pos) > 0:
        print(dup_pos.sort_values(["chart_date", "current_position"])[["chart_date", "current_position", "title", "artist_name"]])

    df_sorted = df.sort_values(["song_id", "chart_date"]).copy()
    df_sorted["computed_weeks"] = df_sorted.groupby("song_id").cumcount() + 1
    mismatch = df_sorted[df_sorted["computed_weeks"] != df_sorted["weeks_on_chart"]]
    print(f"\n[5] Rows where computed cumulative weeks != reported weeks_on_chart: {len(mismatch)}")
    if len(mismatch) > 0:
        print(mismatch[["chart_date", "title", "artist_name", "weeks_on_chart", "computed_weeks"]].head(20))
        if len(mismatch) > 20:
            print(f"... and {len(mismatch) - 20} more")

    new_but_not_week1 = df[(df["last_week_position"] == "NEW") & (df["weeks_on_chart"] != 1)]
    week1_but_not_new = df[(df["weeks_on_chart"] == 1) & (df["last_week_position"] != "NEW")]
    print(f"\n[6] Rows flagged NEW but weeks_on_chart != 1: {len(new_but_not_week1)}")
    if len(new_but_not_week1) > 0:
        print(new_but_not_week1[["chart_date", "title", "artist_name", "weeks_on_chart"]].head(10))
    print(f"[7] Rows with weeks_on_chart == 1 but not flagged NEW: {len(week1_but_not_new)}")
    if len(week1_but_not_new) > 0:
        print(week1_but_not_new[["chart_date", "title", "artist_name", "last_week_position"]].head(10))

    df_sorted["prev_weeks"] = df_sorted.groupby("song_id")["weeks_on_chart"].shift(1)
    decreasing = df_sorted[df_sorted["weeks_on_chart"] < df_sorted["prev_weeks"]]
    print(f"\n[8] Rows where weeks_on_chart decreased from the song's previous appearance: {len(decreasing)}")
    if len(decreasing) > 0:
        print(decreasing[["chart_date", "title", "artist_name", "prev_weeks", "weeks_on_chart"]].head(10))

    print("\n[9] Nulls in critical fields:")
    for col in ["title", "artist_name", "current_position"]:
        print(f"    {col}: {df[col].isna().sum()}")

    bad_pos = df[df["current_position"] < 1]
    print(f"\n[10] Rows with current_position < 1: {len(bad_pos)}")
    if len(bad_pos) > 0:
        print(bad_pos[["chart_date", "current_position", "title"]].head(10))

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", required=True)
    parser.add_argument("--raw", default=None)
    args = parser.parse_args()
    check_new_chart(args.chart, raw_path=args.raw)