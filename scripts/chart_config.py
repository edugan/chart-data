CHARTS = {
    "hot-100": {"slug": "hot-100", "start_date": "1958-08-04"},
    "billboard-200": {"slug": "billboard-200", "start_date": "1963-08-17"},
    "pop-radio": {"slug": "pop-songs", "start_date": "1992-10-03"},
    "country-radio": {"slug": "country-airplay", "start_date": "1990-01-20"},
    "alt-radio": {"slug": "alternative-airplay", "start_date": "1988-09-10"},
}

# Derived for backward compatibility with existing callers (scripts/scraper.py
# imports get_chart_slug; nothing needs CHART_URL_SLUGS directly anymore, but
# keeping it around costs nothing and avoids an unnecessary breaking change).
CHART_URL_SLUGS = {name: info["slug"] for name, info in CHARTS.items()}


def get_chart_slug(chart_name):
    if chart_name not in CHARTS:
        raise ValueError(
            f"Unknown chart '{chart_name}'. Add it to CHARTS in scripts/chart_config.py."
        )
    return CHARTS[chart_name]["slug"]


def get_chart_start_date(chart_name):
    """The date backfill.py originally started from for this chart -- also
    the date the routine pipeline re-checks from on every run (cheap: it's
    just a set-membership check against already-scraped dates, real HTTP
    requests only happen for genuinely new weeks)."""
    if chart_name not in CHARTS:
        raise ValueError(
            f"Unknown chart '{chart_name}'. Add it to CHARTS in scripts/chart_config.py."
        )
    return CHARTS[chart_name]["start_date"]