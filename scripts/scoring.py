import numpy as np

def hot100_points(position):
    """Points for a Hot 100 chart position, derived from real chart point estimates."""
    k = position
    return -0.19924 * np.log(k) + 0.000515899 * (k - 1) + 1


def billboard200_points(position):
    """Points for a Billboard 200 chart position, derived from real units data."""
    k = position
    return ((k - 0.31072) / (1 - 0.31072)) ** (-0.523826)


# Only charts listed here get point-scoring / song-totals treatment.
# Charts not listed simply aren't eligible for build_song_totals.py.
SCORING_FUNCTIONS = {
    "hot-100": hot100_points,
    "billboard-200": billboard200_points,
}