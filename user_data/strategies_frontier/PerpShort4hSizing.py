"""Size by coincidence: the last measured mechanism this project has not used.

`PREREG_SIZING_COINCIDENCE_2026-09-29.md`. Entry, stop, target, time stop,
universe, liquidity band, costs and the circuit breaker are all INHERITED
UNCHANGED. The ONLY difference is position size, and total portfolio risk is held
constant so the comparison is a redistribution rather than a leverage change.

THE MECHANISM (measured, and independent of any strategy P&L)
------------------------------------------------------------
`market_check.py`, 515 perps, forward 42-bar equal-weight panel return at every
bar the panel signalled:

    1 signalled  -1.465% (t -3.26)      5-7  -2.645% (t -2.14)
    2           -1.928% (t -2.27)      8-12 -1.583% (t -1.20)
    3-4         -1.950% (t -1.99)      13+  -4.678% (t -4.61)

The 13+ bucket's market move is ~3x every other bucket's. That is a live-
observable quantity (count the symbols that signalled on this bar), unlike the
forward panel return itself, which is why it was never actionable before.

HOW THE COUNT IS OBTAINED WITHOUT LOOKING AT THE FUTURE
--------------------------------------------------------
`n_coincident` for a bar is the number of PAIRS whose signal series is 1 on that
bar. It is read from the analysed dataframe of every pair, so it is known at the
close of the bar - the same moment the entry signal itself is decided, and the
entry fills on the NEXT bar's open. There is no lookahead, and the
truncation causality gate in `test_causality.py` covers the base strategy;
this class adds a read of a column derived from other pairs' CURRENT bars, which
is the same information the engine already has at that timestamp.

Q IS NOT A SEARCHED PARAMETER
-----------------------------
Q is the 85th percentile of the per-bar coincidence distribution, which on this
panel is 13. It was fixed in the prereg before the run.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("user_data", "strategies_frontier"))
sys.path.insert(0, os.path.join("user_data", "strategies"))

from freqtrade.persistence import Trade  # noqa: E402

from PerpShort4hStop import PerpShort4hStop  # noqa: E402


class PerpShort4hSizing(PerpShort4hStop):
    """Frozen rule; position size is scaled by how many symbols signalled together."""

    _sigs: dict | None = None
    _counts: pd.Series | None = None

    @classmethod
    def coincidence(cls, strategy) -> pd.Series:
        """Per-bar count of pairs whose signal series is 1.

        ⚠ THE FIRST VERSION READ `dp._cached_pairs`, which does not exist in
        this freqtrade (the attribute is name-mangled to
        `_DataProvider__cached_pairs`), and it also read the ALREADY-ANALYSED
        frames - which is order-dependent: `populate_indicators` runs once per
        pair, so at the time the first pair is processed the other 99 have not
        been analysed and the count is badly understated. **A count that depends
        on analysis order is a silent wrong number, not a slow one.**

        So the count is ACCUMULATED: each pair's own signal series is stored as
        it is computed, and the running count is rebuilt on every call. It is
        then correct regardless of pair order, and it costs one O(pairs) pass per
        pair, which for 100 symbols x 8,000 bars is a second or two.
        """
        if cls._sigs is None:
            cls._sigs = {}
        if cls._counts is None:
            cls._counts = pd.Series(dtype="float64")

    def populate_indicators(self, dataframe, metadata: dict):
        out = super().populate_indicators(dataframe, metadata)
        pair = (metadata or {}).get("pair") or "X"
        t = pd.to_datetime(out["date"], utc=True)
        # accumulate THIS pair's signal, then rebuild the cross-sectional count
        cls = type(self)
        if cls._sigs is None:
            cls._sigs = {}
        cls._sigs[pair] = pd.Series(
            out["shark_short"].to_numpy(dtype="float64"), index=t)
        wide = pd.concat(list(cls._sigs.values()), axis=1).sort_index()
        counts = wide.fillna(0.0).sum(axis=1)
        out["n_coincident"] = counts.reindex(t).to_numpy()
        # a bar where this pair is the only one analysed yet would read 1; that
        # is the honest floor and the sizing rule then takes the SMALL size, so
        # an undercount can never make the strategy take MORE risk than intended
        out.loc[out["n_coincident"] < 1.0, "n_coincident"] = 1.0
        return out

    def populate_entry_trend(self, dataframe, metadata: dict):
        out = super().populate_entry_trend(dataframe, metadata)
        out["enter_tag"] = np.where(out["shark_short"],
                                    "panel_down_breakout", "")
        return out

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, entry_tag, side, **kwargs):
        base = super().custom_stake_amount(pair, current_time, current_rate,
                                          proposed_stake, min_stake, max_stake,
                                          entry_tag, side, **kwargs)
        q = float(self.config.get("coincidence_q", 13))
        mult_hi = float(self.config.get("coincidence_size_high", 1.0))
        mult_lo = float(self.config.get("coincidence_size_low", 0.5))
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        n = 1.0
        if df is not None and not df.empty and "n_coincident" in df:
            n = float(df["n_coincident"].iloc[-1])
        m = mult_hi if n >= q else mult_lo
        return float(min(base * m, max_stake))
