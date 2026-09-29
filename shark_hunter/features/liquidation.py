"""Liquidation features (spec section 15).

DATA STATUS: no free public source of historical liquidation volume exists.
See :data:`shark_hunter.data.sources.LIQUIDATION_COVERAGE` for the evidence.

The functions are implemented and unit tested against synthetic input so the
pipeline is ready the moment a feed is plugged in.  On real data today they
receive a frame without the liquidation columns and return it unchanged, and
:func:`shark_hunter.data.loader.build_dataset` records the gap in
``Dataset.unavailable`` so it surfaces in the report rather than silently
producing an all-NaN strategy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED = ["long_liquidation_volume", "short_liquidation_volume",
            "total_liquidation_volume"]


def add_liquidation(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    out = df.copy()
    if not all(c in out.columns for c in REQUIRED):
        for c in REQUIRED:
            out[c] = np.nan
        out["liquidation_ratio"] = np.nan
        out["long_liquidation_ratio"] = np.nan
        out["short_liquidation_ratio"] = np.nan
        return out

    out = out.fillna({c: 0.0 for c in REQUIRED})

    for side, col in (("total", "liquidation_ratio"),
                      ("long", "long_liquidation_ratio"),
                      ("short", "short_liquidation_ratio")):
        vol = out[f"{side}_liquidation_volume"]
        base = vol.rolling(window, min_periods=max(5, window // 2)).mean().shift(1)
        out[col] = vol / base.replace(0.0, np.nan)

    out["liquidation_side"] = np.select(
        [out["short_liquidation_volume"] > out["long_liquidation_volume"],
         out["long_liquidation_volume"] > out["short_liquidation_volume"]],
        ["short", "long"],
        default="balanced",
    )
    return out


def liquidation_data_status() -> dict:
    from ..data.sources import LIQUIDATION_COVERAGE
    return dict(LIQUIDATION_COVERAGE)
