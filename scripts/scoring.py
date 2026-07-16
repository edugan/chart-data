def _general_points(k, d, b, c):
    """
    Shared functional form behind all point formulas:
    ((k - d) / (1 - d)) ^ (-b - c*(k - 1))
    """
    exponent = -b - c * (k - 1)
    return ((k - d) / (1 - d)) ** exponent


# Each chart's (d, b, c) parameters, fit from real chart-points/units data.
POINT_PARAMS = {
    "hot-100":       dict(d=-1.2826,   b=0.36673,  c=0.0016766),
    "billboard-200": dict(d=0.255287,  b=0.543096, c=0.000284569),
    "pop-radio":     dict(d=-2.0307,   b=0.351007, c=0.020407),
    "country-radio": dict(d=-2.0307,   b=0.351007, c=0.020407),
    "alt-radio":     dict(d=-2.0307,   b=0.351007, c=0.020407),
}


def _make_points_fn(d, b, c):
    return lambda k: _general_points(k, d, b, c)


SCORING_FUNCTIONS = {
    chart_name: _make_points_fn(**params)
    for chart_name, params in POINT_PARAMS.items()
}