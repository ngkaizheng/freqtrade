"""Target-R frontier: ONE parameter varies, everything else frozen.

SEPARATE FILE ON PURPOSE. `PerpShort4h` is the FROZEN baseline (docs-myself/
PREREG_WIDE_PANEL_2026-09-27.md) and must stay byte-reproducible. Editing it to
accept a config-driven target would let a later reader change the yardstick
without noticing, which is precisely how a baseline gets quietly moved - the
failure `RegimeBreakoutExitStudy` records, where the ATR was measured with the
LATEST value instead of the ENTRY-bar value and every comparison drawn against
it afterwards was silently wrong.

So: the entry, the stop, the regime filter and the time stop are INHERITED
UNCHANGED from PerpShort4h. Only the profit target differs, and only
`target_r = None` disables it.

Read `docs-myself/PREREG_TARGET_R_2026-09-28.md` before believing a number here.
That file is frozen, it forbids picking a cell, and it says plainly that this
hypothesis was generated from the sample it is tested on.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join("user_data", "strategies"))

from freqtrade.persistence import Trade  # noqa: E402

from PerpShort4h import PerpShort4h  # noqa: E402


class PerpShort4hTarget(PerpShort4h):
    """Frozen entry/stop/filter/time-stop; the 2R target is the only variable."""

    def custom_exit(self, pair: str, trade: Trade, current_time, current_rate: float,
                    current_profit: float, **kwargs) -> str | None:
        target_r = self.config.get("target_r", self.target_r)
        stop_price = self._anchor_stop_price(pair, trade)
        risk = None
        if stop_price is not None:
            lev = trade.leverage or 1.0
            risk = stop_price - trade.open_rate * lev
        if target_r is not None and risk is not None and risk > 0:
            lev = trade.leverage or 1.0
            target = trade.open_rate * lev - float(target_r) * risk
            if current_rate <= target:
                return f"target_{target_r:g}R"
        # time stop is inherited EXACTLY: seconds per bar = timeframe_min * 60
        held = ((current_time - trade.open_date_utc).total_seconds()
                / (self.timeframe_min * 60))
        if held >= self.time_stop_bars:
            return "time_stop"
        return None
