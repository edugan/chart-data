import argparse
import os
import pandas as pd
import json


def build_weekly_peer_summary(chart_name, runs_path=None, out_path=None):
    """
    Aggregates closed (non-active) runs by peak week, storing each week's
    raw list of run_total_points values. This is the pre-summarized table
    that scoring pulls ~208 nearby weeks from, instead of scanning the full
    runs table every time a song needs to be scored.

    Active runs are excluded entirely here, since they're never used as
    peers -- they only ever get scored themselves, using this same summary
    for their peer pool.
    """
    runs_path = runs_path or f"data/processed/{chart_name}_runs.parquet"
    out_path = out_path or f"data/processed/{chart_name}_weekly_peer_summary.parquet"

    runs = pd.read_parquet(runs_path)
    closed = runs[~runs["is_active"]]

    summary = (
        closed.groupby("peak_week")
        .agg(
            points_list=("run_total_points", list),
            run_ids=("run_id", list),
            n_runs=("run_total_points", "size"),
        )
        .reset_index()
        .sort_values("peak_week")
        .reset_index(drop=True)
    )

    # Store the list columns as JSON strings rather than native parquet list
    # columns -- pandas/pyarrow have a known bug reading back list-of-string
    # columns (list-of-float round-trips fine, but we serialize both for
    # consistency and to avoid relying on that distinction holding forever).
    # Elements are explicitly cast to native Python types first, since
    # .agg(..., list) can hand back numpy arrays/scalars depending on the
    # pandas version, which json.dumps can't serialize directly.
    summary["points_list"] = summary["points_list"].apply(lambda lst: json.dumps([float(v) for v in lst]))
    summary["run_ids"] = summary["run_ids"].apply(lambda lst: json.dumps([str(v) for v in lst]))
    
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    summary.to_parquet(out_path, index=False)
    print(f"-> Saved weekly peer summary with {len(summary)} weeks to {out_path}")
    print(f"   Total closed runs represented: {summary['n_runs'].sum()} "
          f"(of {len(runs)} total runs, {runs['is_active'].sum()} still active)")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--runs", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    build_weekly_peer_summary(args.chart, runs_path=args.runs, out_path=args.out)