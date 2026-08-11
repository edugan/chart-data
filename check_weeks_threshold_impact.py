import argparse
import pandas as pd


def check_weeks_threshold_impact(chart_name, runs_path=None):
    """
    Shows, per peak year, how many runs survive at various minimum
    weeks-charted thresholds. Run this BEFORE deciding whether/where to
    set a peer-eligibility floor -- the goal is to see whether one-week
    (or two-week) "album bomb" style entries are concentrated in specific
    eras (as expected for the streaming era) or fairly spread out
    historically (in which case a floor mostly just trims noise evenly).
    """
    runs_path = runs_path or f"data/processed/{chart_name}_runs.parquet"
    runs = pd.read_parquet(runs_path)

    if "n_weeks_charted" not in runs.columns:
        raise ValueError(
            "n_weeks_charted column not found -- rerun build_chart_runs.py "
            "after adding n_weeks_charted=('tracking_week_start', 'size') "
            "to its aggregation step."
        )

    runs = runs.copy()
    runs["peak_year"] = pd.to_datetime(runs["peak_week"]).dt.year

    summary = runs.groupby("peak_year").agg(
        all_runs=("run_id", "size"),
        min2=("n_weeks_charted", lambda s: (s >= 2).sum()),
        min3=("n_weeks_charted", lambda s: (s >= 3).sum()),
    )
    summary["pct_dropped_min2"] = 100 * (1 - summary["min2"] / summary["all_runs"])
    summary["pct_dropped_min3"] = 100 * (1 - summary["min3"] / summary["all_runs"])

    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 120)
    print(summary.round(1))

    print()
    print("Decade-level summary (average % dropped):")
    summary["decade"] = (summary.index // 10) * 10
    print(summary.groupby("decade")[["pct_dropped_min2", "pct_dropped_min3"]].mean().round(1))

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--runs", default=None)
    args = parser.parse_args()
    check_weeks_threshold_impact(args.chart, runs_path=args.runs)