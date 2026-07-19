import argparse
import os
import pandas as pd

from scripts.era_scoring import score_run, load_peer_summary, PeerIndex, WINDOW_WEEKS


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
        })

    new_scores = pd.DataFrame(records)

    if existing is not None:
        # Keep the untouched finalized rows from the existing file, replace everything else
        kept = existing[existing["run_id"].isin(already_finalized_ids)]
        combined = pd.concat([kept, new_scores], ignore_index=True)
    else:
        combined = new_scores

    combined = combined.sort_values("peak_week").reset_index(drop=True)

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

    compute_era_scores(
        args.chart,
        mode=args.mode,
        runs_path=args.runs,
        peer_summary_path=args.peer_summary,
        out_path=args.out,
    )