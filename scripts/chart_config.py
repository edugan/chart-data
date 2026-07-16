CHART_URL_SLUGS = {
    "hot-100": "hot-100",
    "billboard-200": "billboard-200",
    "pop-radio": "pop-songs",
    "country-radio": "country-airplay",
    "alt-radio": "alternative-airplay",
}

def get_chart_slug(chart_name):
    if chart_name not in CHART_URL_SLUGS:
        raise ValueError(
            f"Unknown chart '{chart_name}'. Add it to CHART_URL_SLUGS in scripts/chart_config.py."
        )
    return CHART_URL_SLUGS[chart_name]