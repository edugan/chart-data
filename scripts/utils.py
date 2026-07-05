from datetime import date, timedelta

def generate_chart_dates(start_date, end_date):
    """
    Returns a sorted list of 'YYYY-MM-DD' strings for every valid Billboard
    Hot 100 chart date between start_date and end_date (inclusive).

    Handles known irregularities:
      - Aug 4, 1958 to Dec 25, 1961: charts dated on Mondays
      - Jan 6, 1962 onward: charts dated on Saturdays
      - Jul 4, 1976 (a Sunday): the chart that would normally be dated
        Sat Jul 3, 1976 was instead dated Jul 4 in honor of the US
        Bicentennial. This replaces that week's date rather than adding one.
      - Jan 3, 2018 (a Wednesday): an extra chart inserted between the
        Saturday charts dated Dec 30, 2017 and Jan 6, 2018.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    dates = []

    # Era 1: Monday charts
    monday_start = date(1958, 8, 4)
    monday_end = date(1961, 12, 25)
    current = monday_start
    while current <= monday_end:
        dates.append(current)
        current += timedelta(weeks=1)

    # Era 2: Saturday charts, with known one-off exceptions
    saturday_start = date(1962, 1, 6)
    current = saturday_start
    phase2_end = max(end, saturday_start)
    while current <= phase2_end:
        if current == date(1976, 7, 3):
            dates.append(date(1976, 7, 4))  # Bicentennial substitution, not an addition
        else:
            dates.append(current)

        if current == date(2017, 12, 30):
            dates.append(date(2018, 1, 3))  # genuine extra chart

        current += timedelta(weeks=1)

    return [d.isoformat() for d in dates if start <= d <= end]