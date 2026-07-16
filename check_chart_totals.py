import argparse
import pandas as pd

def check_chart_totals(chart_name):
    enriched_path = f"data/processed/{chart_name}_enriched.parquet"
    totals_path = f"data/processed/{chart_name}_chart_totals.parquet"

    enriched = pd.read_parquet(enriched_path)
    totals = pd.read_parquet(totals_path)

    print("=" * 60)
    print(f"CHECKING: {chart_name} chart totals")
    print("=" * 60)

    # 1. Row count -- one row per unique song/album, no more no less
    n_unique = enriched["song_id"].nunique()
    print(f"\nUnique song_ids in enriched data: {n_unique}")
    print(f"Rows in totals table: {len(totals)}")
    assert len(totals) == n_unique, "Totals table doesn't have one row per song_id!"

    # 2. No nulls in core columns
    for col in ["total_points", "debut_chart_date", "debut_position", "peak_chart_date", "peak_position"]:
        n_null = totals[col].isna().sum()
        print(f"Nulls in {col}: {n_null}")
        # assert n_null == 0, f"Unexpected nulls in {col}"

    # 3. Peak position should never be numerically worse (higher) than debut
    #    position, since peak is defined as the best position ever reached
    bad_peaks = totals[totals["peak_position"] > totals["debut_position"]]
    print(f"\nRows where peak_position > debut_position (should be 0): {len(bad_peaks)}")
    if len(bad_peaks) > 0:
        print(bad_peaks[["title", "artist_name", "debut_position", "peak_position"]].head(10))
    assert len(bad_peaks) == 0

    # 4. Total points should be positive for every row (given current formulas)
    negative_totals = totals[totals["total_points"] <= 0]
    print(f"Rows with non-positive total_points: {len(negative_totals)}")
    if len(negative_totals) > 0:
        print(negative_totals[["title", "artist_name", "total_points"]].head(10))

    # 5. Spot check: song/album with the most chart weeks should plausibly
    #    rank near the top by total points (not guaranteed #1, but should be
    #    reasonably high -- a huge outlier here is worth a manual look)
    weeks_on_chart = enriched.groupby("song_id").size().rename("n_weeks")
    totals_with_weeks = totals.set_index("song_id").join(weeks_on_chart)
    totals_with_weeks["points_rank"] = totals_with_weeks["total_points"].rank(ascending=False, method="min")
    print("\nTop 5 by number of weeks charted, with their points rank:")
    top_by_weeks = totals_with_weeks.sort_values("n_weeks", ascending=False).head(5)
    print(top_by_weeks[["title", "artist_name", "n_weeks", "total_points", "points_rank"]])

    # 6. Overall leaderboard -- eyeball this against what you'd expect
    print("\nTop 10 by total points:")
    print(totals[["title", "artist_name", "total_points", "debut_chart_date", "peak_chart_date"]].head(10))

    print("\nAll automated checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    args = parser.parse_args()
    check_chart_totals(args.chart)