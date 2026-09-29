"""Rolling walk-forward evaluation (spec section 39).

The spec forbids shuffling and asks for chronological splits with a rolling
window.  Because this study uses pre-registered, non-optimised parameters, the
walk-forward is not a parameter search -- it is a *stability* test: does the
strategy hold up in every consecutive out-of-sample window, or was the
headline number carried by one lucky stretch?
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .. import config as C


def rolling_windows(start: dt.datetime, end: dt.datetime,
                    window_months: int = 6,
                    step_months: int = 3) -> list[tuple[dt.datetime, dt.datetime]]:
    """Chronological train/validate/OOS triplets, no shuffling."""
    out = []
    cur = start
    while cur < end:
        oos_start = _add_months(cur, window_months)
        oos_end = _add_months(oos_start, step_months)
        if oos_end > end:
            oos_end = end
        if oos_start >= end:
            break
        # (train_start, train_end, oos_start, oos_end)
        out.append((cur, oos_start, oos_start, oos_end))
        cur = _add_months(cur, step_months)
    return out


def _add_months(d: dt.datetime, months: int) -> dt.datetime:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return d.replace(year=year, month=month)


def walk_forward(evaluate, *, start: dt.datetime | None = None,
                 end: dt.datetime | None = None,
                 window_months: int = 6, step_months: int = 3) -> pd.DataFrame:
    """Run ``evaluate(train_start, train_end, oos_start, oos_end)`` per window.

    ``evaluate`` returns a dict of metrics for the OOS window.  The training
    window is passed so a caller that *does* optimise can; this study does not,
    and its fixed parameters are recorded instead.
    """
    start = start or C.STUDY_START
    end = end or C.STUDY_END
    rows = []
    for tr_s, tr_e, oos_s, oos_e in rolling_windows(start, end, window_months, step_months):
        m = evaluate(tr_s, tr_e, oos_s, oos_e)
        if m is None:
            continue
        rows.append({"train_start": tr_s, "train_end": tr_e,
                     "oos_start": oos_s, "oos_end": oos_e, **m})
    return pd.DataFrame(rows)


def degradation(train_metrics: dict, oos_metrics: dict) -> dict:
    """How much of the in-sample result survived out of sample.

    A ratio near 1.0 is suspicious in the other direction: a strategy whose OOS
    result matches IS almost exactly as likely to be noise as one that decays.
    """
    out = {}
    for key in ("expectancy_r", "profit_factor_r", "hit_rate_r", "total_trades"):
        a, b = train_metrics.get(key), oos_metrics.get(key)
        if a is None or b is None or not np.isfinite(a) or a == 0:
            continue
        out[f"{key}_is"] = a
        out[f"{key}_oos"] = b
        out[f"{key}_retention"] = b / a
    return out
