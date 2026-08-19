"""
Runs the full processing chain for every chart in scripts/chart_config.CHARTS:
backfill (scrape any new weeks) -> enrich -> runs -> weekly peer summary ->
era scores (routine mode) -> chart totals.

Meant to be invoked by the scheduled GitHub Actions workflow, but works
identically run locally (`python run_pipeline.py` or
`python run_pipeline.py --charts hot-100` to test just one chart without
touching the others).

Each chart is fully independent: if one chart's scrape or a downstream step
throws, that failure is logged and the run moves on to the rest -- a single
flaky request or a not-yet-published chart week should never block the other
charts from getting their update. The script exits non-zero if ANY chart
failed, so a scheduled run is still visibly flagged even though the charts
that succeeded still got their data committed (see the workflow yaml, which
commits with `if: always()` for exactly this reason).
"""
import argparse
import sys
import traceback
from datetime import date, timedelta

from scripts.chart_config import CHARTS
from scripts.scoring import SCORING_FUNCTIONS
from backfill import backfill
from build_enriched_dataset import build_enriched_dataset
from build_chart_runs import build_chart_runs
from build_weekly_peer_summary import build_weekly_peer_summary
from compute_era_scores import compute_era_scores
from build_chart_totals import build_chart_totals


def next_chart_date_target(today=None):
    """
    The chart date actually worth checking for as of today. Billboard labels
    each week's chart with the UPCOMING Saturday but publishes it days
    earlier (typically the preceding Tuesday) -- so on a normal Tuesday,
    "today" itself is not a valid chart date, and generate_chart_dates()
    would never include the Saturday that's actually live right now if we
    naively used date.today() as the end_date. All 5 current charts are
    Saturday-dated in the modern era (none predate the 1962 switch), so
    "next Saturday on or after today" is the correct target across the
    board. If today already IS that Saturday, this returns today unchanged.
    """
    today = today or date.today()
    days_ahead = (5 - today.weekday()) % 7  # Monday=0 ... Saturday=5
    return (today + timedelta(days=days_ahead)).isoformat()


def run_chart(chart_name, start_date, end_date):
    print(f"\n{'=' * 70}\n{chart_name}\n{'=' * 70}")

    raw_path = f"data/raw/{chart_name}.csv"
    backfill(chart_name, start_date=start_date, end_date=end_date, out_path=raw_path)
    build_enriched_dataset(chart_name)

    # Scoring is a deliberately manual, per-chart onboarding step (fitting
    # POINT_PARAMS in scripts/scoring.py) -- a chart with raw+enriched data
    # but no scoring formula yet is a normal, expected state (raw browsing
    # in the dashboard already works), NOT a failure. build_chart_runs.py
    # requires SCORING_FUNCTIONS membership unconditionally, so check here
    # rather than letting that raise and get logged as a real error.
    if chart_name not in SCORING_FUNCTIONS:
        print(f"-> No scoring formula yet for '{chart_name}' -- skipping runs/peer-summary/"
              f"era-scores/chart-totals. Raw data is up to date; add POINT_PARAMS in "
              f"scripts/scoring.py when ready to score this chart.")
        return

    build_chart_runs(chart_name)  # split_runs=True default, per current policy for every chart
    build_weekly_peer_summary(chart_name)  # min_weeks_for_peer=1 default, unchanged
    compute_era_scores(chart_name, mode="routine")
    build_chart_totals(chart_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--charts", default=None,
        help="Comma-separated chart names to run (default: all charts in CHARTS).",
    )
    args = parser.parse_args()

    chart_names = args.charts.split(",") if args.charts else list(CHARTS.keys())
    target_date = next_chart_date_target()
    print(f"Target chart date for this run: {target_date}")
    failures = []

    for chart_name in chart_names:
        if chart_name not in CHARTS:
            print(f"!!! Skipping unknown chart '{chart_name}' (not in scripts/chart_config.CHARTS)")
            failures.append(chart_name)
            continue
        try:
            run_chart(chart_name, CHARTS[chart_name]["start_date"], target_date)
        except Exception:
            print(f"\n!!! {chart_name} FAILED:")
            traceback.print_exc()
            failures.append(chart_name)

    print(f"\n{'=' * 70}")
    if failures:
        print(f"Done, but with failures in: {failures}")
        sys.exit(1)
    print("All charts updated successfully.")


if __name__ == "__main__":
    main()