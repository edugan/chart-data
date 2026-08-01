import argparse
import os
import pandas as pd
import numpy as np

from scripts.era_scoring import score_run, load_peer_summary, PeerIndex, WINDOW_WEEKS

# Reference effective peer count for the volume-adjusted score (see below).
# This is a FIXED constant, not recomputed per-run: it only shifts every
# song's volume-adjusted score by the same amount, so its exact value has
# zero effect on rankings -- it just sets what a "typical" adjusted score
# looks like on the display scale. Picked to be roughly in the middle of
# the range of n_eff actually seen across hot-100 history so the adjusted
# column is easy to eyeball against the raw era_score column.
V_REF_N_EFF = 2000

def compute_era_scores(chart_name, mode="routine", runs_path=None, peer_summary_path=None, out_path=None):
    """
    Computes era-adjusted hazard scores for a chart's runs.

    mode="routine": only (re)computes runs that aren't yet finalized (their
        2-year peer window hasn't fully closed against the latest available
        data) or that don't have a score yet at all. Already-finalized runs
        keep their existing stored score untouched.
    mode="global": recomputes every run from scratch. Use this after a
        change to the scoring methodology itself.
    """
    assert mode in ("routine", "global"), "mode must be 'routine' or 'global'"

    runs_path = runs_path or f"data/processed/{chart_name}_runs.parquet"
    peer_summary_path = peer_summary_path or f"data/processed/{chart_name}_weekly_peer_summary.parquet"
    out_path = out_path or f"data/processed/{chart_name}_era_scores.parquet"

    runs = pd.read_parquet(runs_path)
    peer_summary = load_peer_summary(peer_summary_path)
    peer_index = PeerIndex(peer_summary)  # built once, reused for every run scored below

    # The latest chart week actually present in the data -- a run is only
    # "finalized" once this is at least WINDOW_WEEKS past its peak week,
    # since no further peers can ever arrive before that point.
    latest_available_week = runs["run_end_week"].max()
    runs["is_finalized"] = (runs["peak_week"] + pd.Timedelta(weeks=WINDOW_WEEKS)) <= latest_available_week

    existing = None
    if mode == "routine" and os.path.exists(out_path):
        existing = pd.read_parquet(out_path)

    if existing is not None:
        already_finalized_ids = set(existing.loc[existing["is_finalized"], "run_id"])
        to_score = runs[~runs["run_id"].isin(already_finalized_ids)].copy()
        print(f"Routine update: {len(already_finalized_ids)} runs already finalized and untouched, "
              f"{len(to_score)} runs to (re)score.")
    else:
        to_score = runs.copy()
        print(f"{'Global' if mode == 'global' else 'Routine (no existing file, scoring all)'} update: "
              f"scoring all {len(to_score)} runs.")

    records = []
    count = 0
    for _, row in to_score.iterrows():
        if count % 500 == 0:
            print(row["peak_week"])
        count = count + 1
        
        result = score_run(
            target_points=row["run_total_points"],
            target_peak_week=row["peak_week"],
            target_run_id=row["run_id"],
            peer_index=peer_index,
        )
        records.append({
            "run_id": row["run_id"],
            "song_id": row["song_id"],
            "title": row["title"],
            "artist_name": row["artist_name"],
            "peak_week": row["peak_week"],
            "peak_position": row["peak_position"],
            "run_total_points": row["run_total_points"],
            "is_active": row["is_active"],
            "is_finalized": row["is_finalized"],
            "era_score": result["score"],
            "score_reason": result["reason"],
            "n_peers": result["n_peers"],
            "n_eff": result.get("n_eff"),
        })

    new_scores = pd.DataFrame(records)

    if existing is not None:
        # Keep the untouched finalized rows from the existing file, replace everything else
        kept = existing[existing["run_id"].isin(already_finalized_ids)]
        combined = pd.concat([kept, new_scores], ignore_index=True)
    else:
        combined = new_scores

    combined = combined.sort_values("peak_week").reset_index(drop=True)

    # Volume-adjusted score: corrects for eras with very different chart
    # throughput (e.g. Hot 100 volume swung from 600-700 songs/year in the
    # 1960s and 2020s down to under 400 -- sometimes under 300 -- in the
    # mid-90s through mid-2000s). era_score answers "how surprising was
    # this specific performance, given everything else happening at the
    # time" -- which correctly gives high-volume eras more top-N
    # representation, since they genuinely produced more extreme outcomes.
    # era_score_volume_adjusted instead answers "how surprising would this
    # be if every era had the same typical number of contenders" -- a
    # multiple-comparisons-style correction, additive in log-hazard space:
    #   H_adjusted = H - log(n_eff) + log(V_REF)
    # (using each run's own effective peer count rather than a raw yearly
    # song count, since that properly discounts distant, low-weight peers
    # instead of treating every peer in the +/-3-year window as a full
    # "vote"). Confirmed by direct simulation: for a fixed target rate of
    # calibrated hazard exceedances, this is the sign that actually
    # equalizes expected top-N representation across eras of very
    # different volume (a naive same-signed-as-H version instead made the
    # imbalance worse, not better). Neither column is more "correct" than
    # the other -- they answer different questions, and both are kept side
    # by side rather than picking one.
    combined["era_score_volume_adjusted"] = (
        combined["era_score"] - np.log(combined["n_eff"]) + np.log(V_REF_N_EFF)
    )

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    combined.to_parquet(out_path, index=False)

    n_unscored = combined["era_score"].isna().sum()
    print(f"-> Saved {len(combined)} era scores to {out_path}")
    print(f"   Finalized: {combined['is_finalized'].sum()}  |  "
          f"Unscored (insufficient peer data): {n_unscored}")

    return combined


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--mode", choices=["routine", "global"], required=True)
    parser.add_argument("--runs", default=None)
    parser.add_argument("--peer-summary", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    # print("!!! CANARY: compute_era_scores.py loaded from:", __file__)
    # print("!!! args.mode =", args.mode)

    compute_era_scores(
        args.chart,
        mode=args.mode,
        runs_path=args.runs,
        peer_summary_path=args.peer_summary,
        out_path=args.out,
    )