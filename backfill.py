import argparse
import os
import time
import random
import pandas as pd

from scripts.scraper import scrape_billboard_chart
from scripts.utils import generate_chart_dates

COLUMNS_ORDER = [
    "chart_date", "current_position", "title", "artist_name",
    "last_week_position", "weeks_on_chart", "debut_position",
    "debut_date", "awards_vector"
]

def backfill(chart_name, start_date, end_date, out_path, checkpoint_every=10, dry_run=False):
    target_dates = generate_chart_dates(start_date, end_date)

    existing_dates = set()
    if not dry_run and os.path.exists(out_path):
        existing = pd.read_csv(out_path)
        existing_dates = set(existing["chart_date"].unique())
        print(f"Found existing file with {len(existing_dates)} dates already scraped.")

    dates_to_fetch = [d for d in target_dates if d not in existing_dates]
    print(f"{len(dates_to_fetch)} of {len(target_dates)} weeks need fetching.")

    if dry_run:
        # Just grab a handful of weeks so you're not waiting on a full backfill to check output
        dates_to_fetch = dates_to_fetch[:3]
        print(f"[DRY RUN] Only fetching {len(dates_to_fetch)} week(s) for a quick look, nothing will be saved.")

    all_rows = []
    for i, target_date in enumerate(dates_to_fetch):
        week_data = scrape_billboard_chart(chart_name, target_date)
        all_rows.extend(week_data)

        time.sleep(1 + random.random())

        if not dry_run and all_rows and (i + 1) % checkpoint_every == 0:
            _save(all_rows, out_path)
            all_rows = []

    if not all_rows:
        print("No data collected." if not dry_run else "No data collected in dry run.")
        return

    df = pd.DataFrame(all_rows)[COLUMNS_ORDER]

    if dry_run:
        pd.set_option('display.max_rows', 200)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        print(f"\n================== DRY RUN PREVIEW ({chart_name}) ==================\n")
        print(df)
    else:
        _save(all_rows, out_path)
        print("Backfill complete.")


def _save(rows, out_path):
    df = pd.DataFrame(rows)[COLUMNS_ORDER]

    if os.path.exists(out_path):
        df.to_csv(out_path, mode="a", header=False, index=False)
    else:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        df.to_csv(out_path, mode="w", header=True, index=False)

    print(f"-> Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", default="data/hot100.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print results instead of saving to file")
    args = parser.parse_args()

    backfill(args.chart, args.start, args.end, args.out, dry_run=args.dry_run)