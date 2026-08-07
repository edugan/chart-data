"""
Quick diagnostic: dumps schema + sample rows from a chart's era_scores
parquet (plus a couple of related files) so it can be pasted back for
review. Run from the repo root.
"""
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

CHART = "hot-100"  # change if you want a different chart

paths = {
    "enriched": f"data/processed/{CHART}_enriched.parquet",
    "era_scores": f"data/processed/{CHART}_era_scores.parquet",
    "runs": f"data/processed/{CHART}_runs.parquet",
    "weekly_peer_summary": f"data/processed/{CHART}_weekly_peer_summary.parquet",
    "chart_totals": f"data/processed/{CHART}_chart_totals.parquet",
}

for label, path in paths.items():
    print("=" * 80)
    print(f"{label}  ({path})")
    print("=" * 80)
    try:
        df = pd.read_parquet(path)
    except FileNotFoundError:
        print("  -> file not found, skipping\n")
        continue

    print(f"shape: {df.shape}")
    print("\ndtypes:")
    print(df.dtypes)

    print("\nnull counts (nonzero only):")
    nulls = df.isna().sum()
    print(nulls[nulls > 0] if (nulls > 0).any() else "  (none)")

    print("\nhead(5):")
    print(df.head(5))

    if label == "enriched":
        for flag_col in ("is_debut", "is_peak"):
            if flag_col in df.columns:
                print(f"\n{flag_col} value counts:")
                print(df[flag_col].value_counts(dropna=False))
        # Look for a song with more than one run's worth of debuts, to check
        # whether is_debut fires again on re-entry after a gap.
        if "is_debut" in df.columns and "song_id" in df.columns:
            debut_counts = df.loc[df["is_debut"], "song_id"].value_counts()
            recurring = debut_counts[debut_counts > 1]
            print(f"\nsongs with >1 is_debut=True row: {len(recurring)}")
            if len(recurring) > 0:
                example_id = recurring.index[0]
                cols = [c for c in ["song_id", "tracking_week_start", "current_position",
                                    "last_week_position", "is_debut", "is_peak"] if c in df.columns]
                print(f"\nexample recurring song_id={example_id!r}, its is_debut=True rows:")
                print(df[(df["song_id"] == example_id) & (df["is_debut"])][cols])

    if label == "era_scores":
        print("\ntop 10 by era_score:")
        print(
            df.sort_values("era_score", ascending=False)
            .head(10)[["title", "artist_name", "peak_week", "era_score",
                       "era_score_volume_adjusted", "n_peers", "n_eff", "is_finalized"]]
        )
        print("\nscore_reason value counts:")
        print(df["score_reason"].value_counts(dropna=False))

    print()