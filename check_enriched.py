import argparse
import pandas as pd

def check_enriched(chart_name):
    raw_path = f"data/raw/{chart_name}.csv"
    enriched_path = f"data/processed/{chart_name}_enriched.parquet"

    raw = pd.read_csv(raw_path, dtype={"chart_date": "string"})
    df = pd.read_parquet(enriched_path)

    print("=" * 60)
    print(f"CHECKING: {chart_name}")
    print("=" * 60)

    # 1. Basic shape / dtypes
    print(f"\nRows: {len(df)}  (raw file has {len(raw)})")
    assert len(df) == len(raw), "Row count mismatch between raw and enriched!"
    print("Columns:", df.columns.tolist())
    print(df.dtypes)

    # 2. Nulls in derived columns -- these should never be null
    for col in ["tracking_week_start", "year", "quarter", "decade", "song_id", "is_debut", "is_peak"]:
        n_null = df[col].isna().sum()
        print(f"Nulls in {col}: {n_null}")
        assert n_null == 0, f"Unexpected nulls in {col}"

    # 3. Rows per chart week -- Hot 100 should mostly be 100, occasionally 99
    #    (missing rows like the Queen case), never more than 100
    per_week = df.groupby("chart_date").size()
    print(f"\nRows per week -- min: {per_week.min()}, max: {per_week.max()}")
    print("Weeks with unusual row counts (not 100):")
    print(per_week[per_week != 100])

    # 4. Debut / weeks_on_chart consistency -- debuts should almost always
    #    have weeks_on_chart == 1. Flag any that don't for a manual look.
    debut_anomalies = df[(df["is_debut"]) & (df["weeks_on_chart"] != 1)]
    print(f"\nDebut rows where weeks_on_chart != 1: {len(debut_anomalies)}")
    if len(debut_anomalies) > 0:
        print(debut_anomalies[["chart_date", "title", "artist_name", "weeks_on_chart"]].head(10))

    # 5. Peak logic spot check -- pick songs with the most total appearances
    #    at position 1 and confirm only ONE of those rows is flagged as peak
    number_ones = df[df["current_position"] == 1]
    peak_number_ones = number_ones[number_ones["is_peak"]]
    counts = number_ones.groupby("song_id").size().sort_values(ascending=False)
    print(f"\nTop 5 songs by weeks at #1:")
    print(counts.head())
    for song_id in counts.head(5).index:
        song_peaks = peak_number_ones[peak_number_ones["song_id"] == song_id]
        print(f"  {song_id}: {len(song_peaks)} peak-flagged row(s) at #1 "
              f"(should be exactly 1)")

    # 6. Quarter/decade format sanity
    bad_quarters = df[~df["quarter"].str.match(r"^\d{4}-[ABCD]$")]
    print(f"\nMalformed quarter labels: {len(bad_quarters)}")
    bad_decades = df[~df["decade"].str.match(r"^\d{4}s$")]
    print(f"Malformed decade labels: {len(bad_decades)}")

    # 7. Known tracking-week edge cases -- eyeball these manually
    edge_dates = ["1976-07-04", "2015-07-18", "2015-07-25", "2018-01-03", "2018-01-06"]
    print("\nEdge-case tracking weeks (verify these by eye):")
    edge_rows = df[df["chart_date"].isin(edge_dates)][
        ["chart_date", "tracking_week_start", "year", "quarter", "decade"]
    ].drop_duplicates()
    print(edge_rows)

    print("\nAll automated checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    args = parser.parse_args()
    check_enriched(args.chart)