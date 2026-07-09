from datetime import date, timedelta

def get_tracking_week_start(chart_date):
    """
    Given a Billboard chart date (str 'YYYY-MM-DD' or date object), returns
    the date the tracking period for that chart actually started. Chart
    dates are posted well after the tracking period ends, and the exact lag
    has changed over time. Use this — not chart_date — to determine which
    calendar quarter/year/decade a chart week "really" belongs to.
    """
    if isinstance(chart_date, str):
        chart_date = date.fromisoformat(chart_date)

    # One-off exceptions checked first, since they'd otherwise fall inside
    # a broader range below with a different (wrong) offset.
    if chart_date == date(1976, 7, 4):
        return chart_date - timedelta(days=20)
    if chart_date == date(2015, 7, 25):
        return chart_date - timedelta(days=26)
    if chart_date == date(2018, 1, 3):
        return chart_date - timedelta(days=19)

    if date(1958, 8, 4) <= chart_date <= date(1961, 12, 25):
        return chart_date - timedelta(days=14)
    if date(1962, 1, 6) <= chart_date <= date(2015, 7, 18):
        return chart_date - timedelta(days=19)
    if date(2015, 8, 1) <= chart_date <= date(2017, 12, 30):
        return chart_date - timedelta(days=22)
    if chart_date >= date(2018, 1, 6):
        return chart_date - timedelta(days=15)

    raise ValueError(f"No tracking-week rule defined for chart date {chart_date}")