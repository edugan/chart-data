"""
Chart discovery and cached data loading.

Charts are discovered dynamically from whatever *_enriched.parquet files
exist in DATA_DIR -- adding chart #6 through #40 later requires no code
changes here, just running the pipeline and dropping the new parquet in
place. A chart additionally supports the era-score views (Leaderboard,
Frame Standings, Diagnostic) only if it also has a matching *_era_scores.parquet,
*_runs.parquet, and *_weekly_peer_summary.parquet.
"""
import glob
import os
import json
import pandas as pd
import streamlit as st

DATA_DIR = "data/processed"


def _chart_name_from_enriched_path(path):
    base = os.path.basename(path)
    suffix = "_enriched.parquet"
    return base[: -len(suffix)] if base.endswith(suffix) else base


def _display_name(chart_name):
    """Human-friendly label. Falls back to the raw slug if no config is found."""
    try:
        from scripts.chart_config import CHART_URL_SLUGS  # optional, may not exist
        for label, slug in CHART_URL_SLUGS.items():
            if slug == chart_name:
                return label
    except Exception:
        pass
    return chart_name.replace("-", " ").title()


@st.cache_data(show_spinner=False)
def discover_charts(_data_dir=DATA_DIR):
    """
    Returns a dict: chart_name -> {
        "display_name": str,
        "has_scoring": bool,   # era_scores + runs + weekly_peer_summary all present
        "paths": {enriched, era_scores, runs, weekly_peer_summary, chart_totals}
    }
    Sorted by display name.
    """
    enriched_paths = sorted(glob.glob(os.path.join(_data_dir, "*_enriched.parquet")))
    charts = {}
    for path in enriched_paths:
        name = _chart_name_from_enriched_path(path)
        paths = {
            "enriched": path,
            "era_scores": os.path.join(_data_dir, f"{name}_era_scores.parquet"),
            "runs": os.path.join(_data_dir, f"{name}_runs.parquet"),
            "weekly_peer_summary": os.path.join(_data_dir, f"{name}_weekly_peer_summary.parquet"),
            "chart_totals": os.path.join(_data_dir, f"{name}_chart_totals.parquet"),
        }
        has_scoring = all(
            os.path.exists(paths[k]) for k in ("era_scores", "runs", "weekly_peer_summary")
        )
        charts[name] = {
            "display_name": _display_name(name),
            "has_scoring": has_scoring,
            "paths": paths,
        }
    return dict(sorted(charts.items(), key=lambda kv: kv[1]["display_name"]))


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


@st.cache_data(show_spinner="Loading chart data...")
def load_enriched(path, _mtime_key=None):
    return pd.read_parquet(path)


@st.cache_data(show_spinner="Loading run data...")
def load_runs(path, _mtime_key=None):
    return pd.read_parquet(path)


@st.cache_data(show_spinner="Loading era scores...")
def load_era_scores(path, _mtime_key=None):
    return pd.read_parquet(path)


@st.cache_data(show_spinner="Loading peer summary...")
def load_weekly_peer_summary(path, _mtime_key=None):
    df = pd.read_parquet(path)
    df["points_list"] = df["points_list"].apply(json.loads)
    df["run_ids"] = df["run_ids"].apply(json.loads)
    return df


def get_enriched(chart):
    p = chart["paths"]["enriched"]
    return load_enriched(p, _mtime(p))


def get_runs(chart):
    p = chart["paths"]["runs"]
    return load_runs(p, _mtime(p))


def get_era_scores(chart):
    p = chart["paths"]["era_scores"]
    return load_era_scores(p, _mtime(p))


def get_weekly_peer_summary(chart):
    p = chart["paths"]["weekly_peer_summary"]
    return load_weekly_peer_summary(p, _mtime(p))


@st.cache_resource(show_spinner="Building peer index...")
def get_peer_index(path, _mtime_key=None):
    """
    Cached PeerIndex, built once per chart per data version (invalidated
    when the weekly_peer_summary file's mtime changes). Uses cache_resource
    rather than cache_data since PeerIndex isn't meant to be treated as a
    copyable value -- it's a bit of reused, immutable in-memory structure.
    """
    from scripts.era_scoring import PeerIndex
    import json as _json

    df = pd.read_parquet(path)
    df["points_list"] = df["points_list"].apply(_json.loads)
    df["run_ids"] = df["run_ids"].apply(_json.loads)
    return PeerIndex(df)


def peer_index_for(chart):
    p = chart["paths"]["weekly_peer_summary"]
    return get_peer_index(p, _mtime(p))