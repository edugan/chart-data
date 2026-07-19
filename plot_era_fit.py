import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scripts.era_scoring import (
    PeerIndex, load_peer_summary, temporal_weight, weighted_quantile,
    adaptive_bandwidths, bulk_pdf, fit_gpd_weighted, score_run,
    WINDOW_WEEKS, TAIL_Q,
)


def find_run(runs, title=None, artist=None, run_id=None):
    if run_id:
        matches = runs[runs["run_id"] == run_id]
    else:
        matches = runs[
            runs["title"].str.lower().str.contains(title.lower())
            & runs["artist_name"].str.lower().str.contains(artist.lower())
        ]
    if len(matches) == 0:
        raise ValueError(f"No matching run found for title={title!r} artist={artist!r} run_id={run_id!r}")
    # if multiple runs match (e.g. a song with more than one chart run), take the highest-scoring one
    return matches.sort_values("run_total_points", ascending=False).iloc[0]


def plot_era_fit(chart_name, title=None, artist=None, run_id=None,
                  runs_path=None, peer_summary_path=None, save_path=None,
                  window_weeks=None):
    """
    Plots a weighted histogram of a target run's peer pool (log-points),
    overlaid with the fitted adaptive-KDE bulk curve and the GPD tail curve,
    so the fit can actually be inspected rather than guessed at. Prints the
    fitted parameters and the resulting score.

    window_weeks: override the module's WINDOW_WEEKS for this plot only,
    useful for comparing e.g. a 2-year vs 3-year window on the same song.
    """
    import scripts.era_scoring as es

    runs_path = runs_path or f"data/processed/{chart_name}_runs.parquet"
    peer_summary_path = peer_summary_path or f"data/processed/{chart_name}_weekly_peer_summary.parquet"

    runs = pd.read_parquet(runs_path)
    peer_summary = load_peer_summary(peer_summary_path)
    peer_index = PeerIndex(peer_summary)

    row = find_run(runs, title=title, artist=artist, run_id=run_id)
    target_points = row["run_total_points"]
    target_week = row["peak_week"]
    target_run_id = row["run_id"]

    window = window_weeks if window_weeks is not None else WINDOW_WEEKS

    points, run_ids, dists = peer_index.query_window(target_week, window)
    mask = run_ids != target_run_id
    points, dists = points[mask], dists[mask]
    weights = temporal_weight(dists)

    log_x = np.log(points)
    target_log_x = np.log(target_points)

    u = weighted_quantile(log_x, weights, 1 - TAIL_Q)
    above = log_x > u
    q = weights[above].sum() / weights.sum()
    h_i = adaptive_bandwidths(log_x, weights)
    xi, sigma = fit_gpd_weighted(log_x[above] - u, weights[above])

    result = score_run(target_points, target_week, target_run_id, peer_index)

    # --- build the plot ---
    grid_max = max(log_x.max(), target_log_x) + 0.5
    grid = np.linspace(log_x.min() - 0.3, grid_max, 500)
    bulk_density = bulk_pdf(grid, log_x, weights, h_i)

    tail_grid = np.linspace(u, grid_max, 200)
    y_grid = tail_grid - u
    if abs(xi) < 1e-8:
        gpd_density = np.exp(-y_grid / sigma) / sigma
    else:
        z = 1 + xi * y_grid / sigma
        gpd_density = (1 / sigma) * np.power(z, -(1 / xi + 1))
    gpd_density_scaled = q * gpd_density  # scaled so its area matches the empirical fraction above u

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(log_x, bins=60, weights=weights, density=True, alpha=0.35,
            label=f"Weighted peer histogram (n={len(points)})", color="steelblue")
    ax.plot(grid, bulk_density, color="navy", lw=2, label="Adaptive KDE (bulk model)")
    ax.plot(tail_grid, gpd_density_scaled, color="crimson", lw=2, ls="--",
            label=f"GPD tail (xi={xi:.3f}, sigma={sigma:.3f})")
    ax.axvline(u, color="gray", ls=":", lw=1.5, label=f"Tail threshold u (top {int(q*100)}%)")
    ax.axvline(target_log_x, color="darkorange", lw=2.5,
               label=f"{row['title']} (log-points={target_log_x:.2f})")

    ax.set_xlabel("log(run total points)")
    ax.set_ylabel("density")
    title_str = f"{row['title']} -- {chart_name}, peak week {target_week.date()}\n"
    title_str += f"score={result['score']:.3f}  n_peers={result['n_peers']}  window=±{window}wk"
    ax.set_title(title_str)
    ax.legend(fontsize=8)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=120)
        print(f"-> Saved plot to {save_path}")
    else:
        plt.show()

    print(f"\nTarget: {row['title']} / {row['artist_name']}")
    print(f"  peak_week={target_week.date()}  points={target_points:.4f}  log_points={target_log_x:.4f}")
    print(f"  n_peers={result['n_peers']}  threshold u={u:.4f}  tail_q_actual={q:.4f}")
    print(f"  gpd_xi={xi:.4f}  gpd_sigma={sigma:.4f}")
    print(f"  SCORE={result['score']:.4f}")

    return fig, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", default="hot-100")
    parser.add_argument("--title", default=None)
    parser.add_argument("--artist", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", default=None, help="Path to save the plot (PNG). If omitted, displays interactively.")
    parser.add_argument("--window-weeks", type=int, default=None, help="Override WINDOW_WEEKS for this plot only")
    args = parser.parse_args()

    plot_era_fit(
        args.chart, title=args.title, artist=args.artist, run_id=args.run_id,
        save_path=args.out, window_weeks=args.window_weeks,
    )