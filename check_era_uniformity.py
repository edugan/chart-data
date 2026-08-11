import argparse
import numpy as np
import pandas as pd


def check_era_uniformity(chart_name, top_n=100, runs_path=None, era_scores_path=None, score_col="era_score"):
    """
    Tests whether the top-N songs (by score_col) are spread evenly across
    chart history, AFTER accounting for how many songs charted in each
    period -- as opposed to evenly across raw calendar time, which is a
    different and inappropriate target given real volume varies a lot by
    era.

    The key idea: index each run by its CHRONOLOGICAL RANK PERCENTILE --
    its position among ALL runs ever, sorted by peak_week, scaled to
    [0,1] -- rather than by peak year or calendar date. This percentile
    moves in fixed increments per SONG, not per unit of TIME, so a dense
    era "covers" a smaller slice of it and a sparse era covers a larger
    slice. Under correctly-calibrated scoring (every song has an equal a
    priori chance of scoring high, purely proportional to how many songs
    existed), the chronological-rank percentiles of the top-N should be
    UNIFORMLY distributed on [0,1] -- volume differences by themselves do
    NOT break this property (confirmed by simulation). A high KS
    statistic against Uniform(0,1) indicates genuine over/under
    representation of some period BEYOND what its volume alone predicts
    -- e.g. the window/kernel pulling in too much influence from outside
    the period that's actually relevant to a song's local peers.

    Use this to compare different WINDOW_WEEKS / HALF_WEIGHT_WEEKS
    settings (or different min_weeks_for_peer settings) against each
    other -- lower KS is better -- rather than as a formal hypothesis
    test. Caveat: at typical top-N sizes (25-200) this has real sampling
    noise; treat it as a comparative tuning signal, not a precise verdict,
    and prefer comparing settings on the SAME top_n each time.
    """
    runs_path = runs_path or f"data/processed/{chart_name}_runs.parquet"
    era_scores_path = era_scores_path or f"data/processed/{chart_name}_era_scores.parquet"

    runs = pd.read_parquet(runs_path).sort_values("peak_week").reset_index(drop=True)
    era_scores = pd.read_parquet(era_scores_path)

    n_total = len(runs)
    runs["chrono_percentile"] = (np.arange(n_total) + 0.5) / n_total

    merged = era_scores.merge(runs[["run_id", "chrono_percentile"]], on="run_id", how="left")
    merged = merged.dropna(subset=[score_col])

    top = merged.sort_values(score_col, ascending=False).head(top_n).copy()
    percentiles = np.sort(top["chrono_percentile"].values)

    n = len(percentiles)
    empirical_cdf = (np.arange(1, n + 1)) / n
    ks_stat = np.max(np.abs(percentiles - empirical_cdf))

    print(f"Top {top_n} by {score_col}: chronological-rank-percentile KS vs Uniform(0,1) = {ks_stat:.4f}")
    print("(lower = more evenly spread across history after accounting for volume; use this to compare settings)")
    print()

    top["peak_year"] = pd.to_datetime(top["peak_week"]).dt.year
    top["decade"] = (top["peak_year"] // 10) * 10
    # print("Decade breakdown of this top-N list:")
    # print(top["decade"].value_counts().sort_index())

    return ks_stat, top


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--score-col", default="era_score")
    parser.add_argument("--runs", default=None)
    parser.add_argument("--era-scores", default=None)
    args = parser.parse_args()
    check_era_uniformity(
        args.chart, top_n=args.top_n, runs_path=args.runs,
        era_scores_path=args.era_scores, score_col=args.score_col,
    )