"""CONTROL ARM: identical to the 4.0-ATR stop arm, with the entry timing destroyed.

WHY THIS FILE EXISTS
--------------------
`PREREG_STOP_MULTIPLE_2026-09-28.md` widened the stop and mean R rose 8x. But the
exit mix shows why that is ambiguous: at 4.0 ATR, **60.7% of trades exit on the
42-bar time stop**, only 7.2% reach 2R, and only 31.4% hit the stop. The strategy
has become "hold for 7 days". "Widening the stop helped" and "holding for 7 days
helped" are the same sentence at that point, and the panel fell a median of
-80.9% over the window, so a 7-day hold in this universe is not a neutral thing to
be handed for free.

`PREREG_STOP_CONTROL_2026-09-28.md` freezes the control: same stop, same filters,
same universe, same costs, same 1x vol-targeted sizing - and an entry signal with
the **same number of bars per pair but no reference to price or volume**.

THE SEED IS FIXED IN CODE AND CANNOT BE RE-ROLLED
-------------------------------------------------
The draw is a deterministic LCG over the bar index, seeded from a hash of the
pair string, computed once per bar in `populate_indicators`. It does not depend
on the run, the timerange, the config, or anything else, so the control is
bit-for-bit reproducible. Re-rolling it until the control looks bad would be the
easiest way to manufacture a result here, so there is no seed parameter to
change.

Note the entry COUNT is matched to the real signal per pair, so trade count,
holding time, notional exposure and the timestamp clustering that the dependence
correction cares about are all comparable. Only the timing is destroyed.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join("user_data", "strategies"))

from freqtrade.persistence import Trade  # noqa: E402

from PerpShort4hStop import PerpShort4hStop  # noqa: E402

# Fixed multiplier for the LCG. Golden-ratio constant, so consecutive bar
# indices give well-spread values. NOT a tuning parameter.
_LCG_A = 2654435761
_LCG_C = 1013904223
_LCG_M = 2 ** 32


def _pair_seed(pair: str) -> int:
    """FNV-1a over the pair name. Stable across processes and platforms."""
    h = 2166136261
    for ch in pair.encode("utf-8"):
        h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    return h


class PerpShort4hControl(PerpShort4hStop):
    """The 4.0-ATR arm with the entry timing destroyed. Everything else identical."""

    def populate_indicators(self, dataframe, metadata: dict):
        df = super().populate_indicators(dataframe, metadata)
        pair = (metadata or {}).get("pair") or "X"
        real = df["shark_short"].to_numpy()

        # match the real signal's frequency on this pair exactly
        n_real = int(real.sum())
        n = len(df)
        if n_real == 0 or n == 0:
            df["control_entry"] = False
            return df

        # deterministic LCG over bar index, seeded by the pair name
        seed = _pair_seed(pair)
        idx = np.arange(n, dtype=np.int64)
        raw = (idx * _LCG_A + seed + _LCG_C) % _LCG_M
        u = raw.astype(np.float64) / _LCG_M

        k = min(n_real, n)
        # choose the k smallest uniforms -> a fixed, reproducible subset
        order = np.argsort(u, kind="stable")[:k]
        mask = np.zeros(n, dtype=bool)
        mask[order] = True
        df["control_entry"] = mask
        df["real_entry"] = real
        return df

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe["enter_tag"] = np.where(dataframe["control_entry"],
                                          "control_random", "")
        dataframe.loc[dataframe["control_entry"], "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata: dict):
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    # ---- diagnostics so the run can be checked rather than trusted ----
    def populate_indicators_check(self) -> None:  # pragma: no cover
        return None
