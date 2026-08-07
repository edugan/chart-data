import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scripts.era_scoring import (
    PeerIndex, load_peer_summary, temporal_weight, weighted_quantile,
    adaptive_bandwidths, bulk_pdf, fit_gpd_weighted, score_run,
    fit_gpd_bootstrap_ensemble, tail_density_ensemble,
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

    # Score can legitimately be None (score_reason="insufficient_peers") for
    # runs whose peer window didn't have enough data for a stable tail fit --
    # thinner/newer charts hit this far more often than e.g. hot-100. Format
    # defensively so that case prints/plots a clear label instead of crashing
    # on f"{None:.3f}".
    if result["score"] is not None:
        score_display = f"{result['score']:.3f}"
    else:
        score_display = f"N/A ({result['reason']})"

    # --- build the plot ---
    grid_max = max(log_x.max(), target_log_x) + 0.5
    grid = np.linspace(log_x.min() - 0.3, grid_max, 500)
    bulk_density = bulk_pdf(grid, log_x, weights, h_i)

    tail_grid = np.linspace(u, grid_max, 200)
    y_grid = tail_grid - u

    # Point-estimate curve (a single illustrative fit -- NOT what scoring
    # actually uses anymore). Clipped so it correctly decays to zero at its
    # own implied ceiling instead of silently vanishing via NaN when xi < 0
    # and y_grid exceeds -sigma/xi (exactly what was happening before).
    if abs(xi) < 1e-8:
        gpd_density = np.exp(-y_grid / sigma) / sigma
    else:
        z = np.clip(1 + xi * y_grid / sigma, 0.0, None)
        with np.errstate(invalid="ignore"):
            gpd_density = (1 / sigma) * np.power(z, -(1 / xi + 1))
        gpd_density = np.where(z <= 0, 0.0, gpd_density)
    gpd_density_scaled = q * gpd_density

    # Ensemble curve -- this IS what scoring actually uses. Computed
    # directly from each replicate's closed-form density (not by numerically
    # differentiating survival, which amplified floating-point noise into
    # a visible wobble, especially for smaller peer pools).
    xi_boot, sigma_boot = fit_gpd_bootstrap_ensemble(log_x[above] - u, weights[above], target_run_id)
    ensemble_density = np.array([tail_density_ensemble(y, xi_boot, sigma_boot) for y in y_grid])
    ensemble_density_scaled = q * ensemble_density

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(log_x, bins=60, weights=weights, density=True, alpha=0.35,
            label=f"Weighted peer histogram (n={len(points)})", color="steelblue")
    ax.plot(grid, bulk_density, color="navy", lw=2, label="Adaptive KDE (bulk model)")
    ax.plot(tail_grid, gpd_density_scaled, color="crimson", lw=1.5, ls="--", alpha=0.6,
            label=f"Point-estimate GPD (xi={xi:.3f}, sigma={sigma:.3f}) -- illustrative only")
    ax.plot(tail_grid, ensemble_density_scaled, color="darkgreen", lw=2, ls="-",
            label="Bootstrap ensemble tail (actual scoring model)")
    ax.axvline(u, color="gray", ls=":", lw=1.5, label=f"Tail threshold u (top {int(q*100)}%)")
    ax.axvline(target_log_x, color="darkorange", lw=2.5,
               label=f"{row['title']} (log-points={target_log_x:.2f})")

    ax.set_xlabel("log(run total points)")
    ax.set_ylabel("density")
    title_str = f"{row['title']} -- {chart_name}, peak week {target_week.date()}\n"
    title_str += f"score={score_display}  n_peers={result['n_peers']}  window=±{window}wk"
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
    print(f"  SCORE={score_display}")

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