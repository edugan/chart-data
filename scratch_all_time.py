import argparse
import pandas as pd

def check_chart_totals(chart_name):
    totals_path = f"data/processed/{chart_name}_era_scores.parquet"

    totals = pd.read_parquet(totals_path)
    totals = totals.sort_values(by='era_score', ascending=False)
    print(totals[["title", "artist_name", "peak_week", "run_total_points", "era_score"]].head(50))
    # min_year = totals['peak_year'].min()
    # max_year = totals['peak_year'].max()
    
    # for year in range(min_year, max_year + 1):
    #     totals = pd.read_parquet(totals_path)
    #     totals = totals[totals['peak_year'] == year]
    #     print('')
    #     print(totals[["title", "artist_name", "total_points", "peak_tracking_week_start"]].head(5))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    args = parser.parse_args()
    check_chart_totals(args.chart)