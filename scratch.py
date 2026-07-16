import argparse
import pandas as pd

def check_chart_totals(chart_name):
    enriched_path = f"data/processed/{chart_name}_enriched.parquet"
    totals_path = f"data/processed/{chart_name}_chart_totals.parquet"

    for year in range(1958,2027):
        totals = pd.read_parquet(totals_path)
        totals = totals[totals['peak_year'] == year]
        print('')
        print(totals[["title", "artist_name", "total_points", "peak_tracking_week_start"]].head(5))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    args = parser.parse_args()
    check_chart_totals(args.chart)