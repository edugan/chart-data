import numpy as np
import pandas as pd
from scipy.special import erf

INV_SQRT_2PI = 1.0 / np.sqrt(2 * np.pi)


def _norm_pdf(z):
    """Standard normal pdf. Hand-written instead of scipy.stats.norm.pdf --
    at the matrix sizes used here (a few thousand peers squared), scipy's
    generic distribution-object overhead alone was the single largest cost
    in the whole scoring pipeline (measured ~3x slower than this)."""
    return INV_SQRT_2PI * np.exp(-0.5 * z ** 2)


def _norm_cdf(z):
    """Standard normal cdf, same rationale as _norm_pdf above."""
    return 0.5 * (1 + erf(z / np.sqrt(2)))


def load_peer_summary(path):
    """
    Loads a weekly peer summary parquet file, decoding the points_list and
    run_ids columns back from JSON strings into real Python lists (they're
    stored as JSON to avoid a pandas/pyarrow bug reading back list-of-string
    columns -- see build_weekly_peer_summary.py).
    """
    import json
    df = pd.read_parquet(path)
    df["points_list"] = df["points_list"].apply(json.loads)
    df["run_ids"] = df["run_ids"].apply(json.loads)
    return df


WINDOW_WEEKS = 156   # +/- 3 years: peers outside this are never considered
HALF_WEIGHT_WEEKS = 52  # +/- 1 year: roughly half the total weight lives here
TAIL_Q = 0.05        # top 5% of peers modeled by the GPD tail instead of the KDE
MIN_EXCEEDANCES = 8  # below this, fall back to pure bulk model (no tail fit)

# Kernel weight: w(d) = (1 - (d/WINDOW_WEEKS)^2)^P_EXPONENT for |d| <= WINDOW_WEEKS,
# else 0. P_EXPONENT is calibrated so that +/-HALF_WEIGHT_WEEKS captures exactly
# half the total weight under the kernel. Solved once via:
#
#   from scipy import integrate, optimize
#   def I(p, a):
#       return integrate.quad(lambda u: (1 - u**2)**p, 0, a)[0]
#   a = HALF_WEIGHT_WEEKS / WINDOW_WEEKS
#   p = optimize.brentq(lambda p: I(p, a)/I(p, 1.0) - 0.5, 0.001, 50)
#
# which gives p ~= 1.163082 for the 3-year window / 1-year half-weight point.
# Hardcoded here so scoring doesn't re-solve this integral on every call.
P_EXPONENT = 1.163082


def temporal_weight(distance_weeks):
    """
    Weight of a peer whose peak week is `distance_weeks` away from the
    target week (can be a scalar or numpy array). Zero beyond WINDOW_WEEKS.
    """
    d = np.abs(np.asarray(distance_weeks, dtype=float))
    u = d / WINDOW_WEEKS
    w = np.where(u <= 1.0, (1 - np.clip(u, 0, 1) ** 2) ** P_EXPONENT, 0.0)
    return w


def weighted_quantile(x, w, q):
    """Weighted quantile via linear interpolation on the weighted CDF."""
    order = np.argsort(x)
    xs, ws = np.asarray(x)[order], np.asarray(w)[order]
    cum_w = np.cumsum(ws) - 0.5 * ws
    cum_w /= ws.sum()
    return np.interp(q, cum_w, xs)


def weighted_silverman_bandwidth(x, w):
    """Weighted version of Silverman's rule-of-thumb pilot bandwidth."""
    n_eff = (w.sum()) ** 2 / (w ** 2).sum()
    wmean = np.average(x, weights=w)
    wvar = np.average((x - wmean) ** 2, weights=w)
    std = np.sqrt(wvar)
    q25 = weighted_quantile(x, w, 0.25)
    q75 = weighted_quantile(x, w, 0.75)
    iqr = q75 - q25
    spread = min(std, iqr / 1.34) if iqr > 0 else std
    if spread <= 0:
        spread = std if std > 0 else 1.0
    return 0.9 * spread * n_eff ** (-1 / 5)


def adaptive_bandwidths(x, w, alpha=0.5, n_bins=200):
    """
    Abramson-style locally adaptive bandwidths: a pilot fixed-bandwidth KDE
    gives a density estimate at each point, and each point's own bandwidth
    is then shrunk (in dense regions) or expanded (in sparse regions)
    relative to that pilot density.

    The pilot density is the dominant cost in the whole scoring pipeline --
    an exact pairwise computation is O(n^2), which at realistic peer-pool
    sizes (a couple thousand peers) was measured as ~90% of total per-run
    scoring time. When there are meaningfully more points than n_bins, the
    pilot density is instead estimated against a coarse weighted grid
    (binned KDE) rather than every individual point -- this cuts the cost
    to O(n * n_bins) with mean relative error ~0.1% (max ~3%) against the
    exact computation, which is far more than accurate enough for a pilot
    density whose only role is steering local bandwidth scaling, not
    determining the final result directly.
    """
    h0 = weighted_silverman_bandwidth(x, w)

    if len(x) > n_bins * 2:
        lo, hi = x.min(), x.max()
        edges = np.linspace(lo, hi, n_bins + 1)
        bin_centers = (edges[:-1] + edges[1:]) / 2
        bin_idx = np.clip(np.digitize(x, edges) - 1, 0, n_bins - 1)
        bin_weights = np.zeros(n_bins)
        np.add.at(bin_weights, bin_idx, w)
        diffs = (x[:, None] - bin_centers[None, :]) / h0
        kern = _norm_pdf(diffs)
        f_pilot = (kern * bin_weights[None, :]).sum(axis=1) / (h0 * bin_weights.sum())
    else:
        diffs = (x[:, None] - x[None, :]) / h0
        kern = _norm_pdf(diffs)
        f_pilot = (kern * w[None, :]).sum(axis=1) / (h0 * w.sum())

    f_pilot = np.clip(f_pilot, 1e-300, None)  # guard against log(0)
    log_g = np.average(np.log(f_pilot), weights=w)
    g = np.exp(log_g)
    lam = (f_pilot / g) ** (-alpha)
    return h0 * lam


def bulk_pdf(x_eval, x, w, h_i):
    """
    Analytic density of the adaptive-bandwidth mixture (companion to
    bulk_cdf) -- used for visualizing the fitted bulk model against a
    histogram of the actual peer data.
    """
    x_eval = np.atleast_1d(x_eval)
    z = (x_eval[:, None] - x[None, :]) / h_i[None, :]
    return (_norm_pdf(z) / h_i[None, :] * w[None, :]).sum(axis=1) / w.sum()


def bulk_cdf(x_eval, x, w, h_i):
    """
    Analytic CDF of the adaptive-bandwidth mixture: a weighted mixture of
    Gaussians, each centered at a peer's log-points value with its own
    bandwidth. Exact given a Gaussian kernel -- no numerical integration.
    """
    x_eval = np.atleast_1d(x_eval)
    z = (x_eval[:, None] - x[None, :]) / h_i[None, :]
    return (_norm_cdf(z) * w[None, :]).sum(axis=1) / w.sum()


def fit_gpd_weighted(y, w):
    """
    Weighted Probability-Weighted-Moments (PWM) fit of a Generalized Pareto
    distribution to exceedances y (y >= 0), per Hosking & Wallis (1987),
    generalized to weighted samples via weighted plotting positions.

    An earlier version used weighted MLE (via a softplus-reparameterized
    xi >= 0 constraint, replacing an even earlier hard-boundary version that
    had its own numerical instability). MLE turned out to have a much more
    serious problem: at realistic tail-sample sizes (~100-200 weighted
    exceedances), it collapses to exactly the xi=0 boundary in the large
    majority of fits even when the true xi is solidly positive (tested:
    true xi=0.4, n=150 -> MLE landed at the xi=0 boundary in 80% of trials,
    median recovered xi=0.0). This is a well-documented small-sample bias
    of GPD shape MLE, and it was silently flattening every era's fitted
    tail toward a plain exponential, understating exactly how rare genuine
    outliers are -- which is what era-adjusted scoring exists to capture.

    PWM has much better small-sample bias behavior for this parameter (same
    test: median recovered xi=0.37-0.38, essentially never hitting the
    boundary), is closed-form (no optimizer, so also faster), and is the
    standard alternative recommended in the extreme value literature
    specifically for this failure mode.

    xi is still floored at 0 (never negative) for the same reason as
    before: a negative xi implies a hard finite upper bound on the
    distribution, which a genuine outlier could fall outside of.
    """
    order = np.argsort(y)
    y_sorted, w_sorted = y[order], w[order]
    cum_w = np.cumsum(w_sorted) - 0.5 * w_sorted
    F = cum_w / w_sorted.sum()  # weighted plotting position

    b0 = np.sum(w_sorted * y_sorted) / w_sorted.sum()
    b1 = np.sum(w_sorted * F * y_sorted) / w_sorted.sum()

    denom = 2 * b1 - b0
    xi = (4 * b1 - 3 * b0) / denom if abs(denom) > 1e-12 else 0.0
    xi = max(xi, 0.0)
    sigma = max(b0 * (1 - xi), 1e-8)
    return xi, sigma


class PeerIndex:
    """
    Flattens a chart's weekly peer summary into sorted numpy arrays, built
    ONCE per chart. Scoring a target run then uses a binary search to pull
    only the nearby window, rather than re-filtering and re-flattening the
    full dataframe (with Python-level iterrows and list unpacking) on every
    single call -- which is what made the original implementation scale
    with total history length instead of window size, and get slower as
    more years of data accumulated.
    """

    def __init__(self, peer_summary):
        peer_summary = peer_summary.sort_values("peak_week").reset_index(drop=True)

        points, run_ids, weeks = [], [], []
        for _, row in peer_summary.iterrows():  # done once per chart, not per target
            wk = row["peak_week"]
            for pt, rid in zip(row["points_list"], row["run_ids"]):
                points.append(pt)
                run_ids.append(rid)
                weeks.append(wk)

        self.points = np.array(points, dtype=float)
        self.run_ids = np.array(run_ids, dtype=object)
        weeks_arr = np.array(weeks, dtype="datetime64[ns]")

        if len(weeks_arr) > 0:
            self.epoch = weeks_arr[0]
            self.week_offset = (weeks_arr - self.epoch) / np.timedelta64(1, "W")
        else:
            self.epoch = pd.Timestamp("1900-01-01")
            self.week_offset = np.array([], dtype=float)

    def query_window(self, target_peak_week, window_weeks):
        """Returns (points, run_ids, distances_weeks) for peers within window_weeks of the target."""
        target_offset = (pd.Timestamp(target_peak_week) - self.epoch) / np.timedelta64(1, "W")
        lo, hi = target_offset - window_weeks, target_offset + window_weeks
        i0 = np.searchsorted(self.week_offset, lo, side="left")
        i1 = np.searchsorted(self.week_offset, hi, side="right")
        distances = self.week_offset[i0:i1] - target_offset
        return self.points[i0:i1], self.run_ids[i0:i1], distances


def score_run(target_points, target_peak_week, target_run_id, peer_index):
    """
    Computes the era-adjusted hazard score H(x) = -log(1 - F(x)) for a run,
    using all peer runs (from a prebuilt PeerIndex) whose peak week falls
    within WINDOW_WEEKS, weighted by temporal distance, excluding the
    target's own run if present. Returns a dict with the score and
    diagnostic info, or a dict with score=None and a `reason` if there
    wasn't enough peer data.
    """
    points, run_ids, dists = peer_index.query_window(target_peak_week, WINDOW_WEEKS)

    self_mask = run_ids != target_run_id
    points, dists = points[self_mask], dists[self_mask]

    if len(points) < MIN_EXCEEDANCES:  # not even enough peers for a stable tail fit
        return {"score": None, "reason": "insufficient_peers", "n_peers": len(points)}

    weights = temporal_weight(dists)

    log_x = np.log(points)
    target_log_x = np.log(target_points)

    u = weighted_quantile(log_x, weights, 1 - TAIL_Q)
    above = log_x > u
    q = weights[above].sum() / weights.sum()  # actual weighted proportion above threshold

    h_i = adaptive_bandwidths(log_x, weights)

    use_tail = above.sum() >= MIN_EXCEEDANCES and q > 0
    if use_tail:
        y = log_x[above] - u
        w_tail = weights[above]
        xi, sigma = fit_gpd_weighted(y, w_tail)
    else:
        xi, sigma = None, None

    if target_log_x <= u or not use_tail:
        Fu = bulk_cdf(np.array([u]), log_x, weights, h_i)[0]
        Fx = bulk_cdf(np.array([target_log_x]), log_x, weights, h_i)[0]
        if use_tail:
            survival = 1 - (1 - q) * (Fx / Fu) if Fu > 0 else 1.0
            H = -np.log(max(survival, 1e-300))
        else:
            survival = 1 - Fx
            H = -np.log(max(survival, 1e-300))
    else:
        y = target_log_x - u
        z = 1 + xi * y / sigma
        z = max(z, 1e-300)
        if abs(xi) < 1e-8:
            log_survival_gpd = -y / sigma
        else:
            log_survival_gpd = -(1 / xi) * np.log(z)
        H = -np.log(q) - log_survival_gpd

    return {
        "score": H,
        "reason": None,
        "n_peers": len(points),
        "threshold_u": u,
        "tail_q_actual": q,
        "gpd_xi": xi,
        "gpd_sigma": sigma,
        "used_tail_model": use_tail,
    }