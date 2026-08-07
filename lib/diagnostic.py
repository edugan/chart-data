"""
Wraps scripts.plot_era_fit.plot_era_fit for inline display: same threshold
marking, same bulk/tail curve rendering as your existing standalone
diagnostic, just returned as a Figure instead of shown via plt.show()
(save_path is pointed at a throwaway temp file purely to route around the
save-vs-show branch -- the PNG itself is discarded, only the returned
Figure object is used).
"""
import tempfile
import os
import streamlit as st

import plot_era_fit


@st.cache_resource(show_spinner="Fitting era model for this run...")
def get_era_fit_figure(chart_name, run_id, mtime_key=None, window_weeks=None):
    with tempfile.TemporaryDirectory() as d:
        fig, result = plot_era_fit(
            chart_name, run_id=run_id,
            save_path=os.path.join(d, "throwaway.png"),
            window_weeks=window_weeks,
        )
    return fig, result