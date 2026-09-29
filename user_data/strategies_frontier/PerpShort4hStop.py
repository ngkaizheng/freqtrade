"""Stop-multiple frontier: ONE parameter varies, everything else byte-frozen.

SEPARATE FILE, AGAIN. `PerpShort4h` is the frozen baseline and must stay
reproducible; editing it to read `atr_stop` from config would let a later reader
move the yardstick without noticing — the exact failure
`RegimeBreakoutExitStudy` records, where the ATR was measured with the LATEST
value instead of the ENTRY-bar value and every comparison drawn against it
afterwards was silently wrong.

The entry, the regime filter, the universe, the time stop, the costs and the 1x
vol-targeted sizing are INHERITED UNCHANGED. `PerpShort4h.custom_stake_amount`
already sizes `risk / (atr_stop * atr_pct)`, so a wider stop automatically
produces a smaller position for the SAME dollar risk — the comparison is
risk-matched and the wider arm is not accidentally a bigger-position arm.

Read `docs-myself/PREREG_STOP_MULTIPLE_2026-09-28.md` first. It forbids picking a
rung, carries a mechanistic gate (S7: the stop-out rate must actually fall), and
states the falsifier up front.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join("user_data", "strategies"))

from freqtrade.persistence import Trade  # noqa: E402

from PerpShort4h import PerpShort4h  # noqa: E402


class PerpShort4hStop(PerpShort4h):
    """Frozen everything; `atr_stop` is the only variable, read from config."""

    @property
    def stop_mult(self) -> float:
        return float(self.config.get("atr_stop", self.atr_stop))

    def _anchor_stop_price(self, pair: str, trade: Trade) -> float | None:
        atr = self.entry_atr(pair, trade)
        if atr is None:
            return None
        lev = trade.leverage or 1.0
        # open_rate is the MARGIN price (divided by leverage); the stop lives in
        # PRICE terms, so the distance is computed in price, not in margin.
        return trade.open_rate * lev + self.stop_mult * atr

    def custom_stake_amount(self, pair: str, current_time, current_rate: float,
                            proposed_stake: float, min_stake, max_stake: float,
                            entry_tag, side: str, **kwargs) -> float:
        """Inherited sizing with the frontier's stop multiple substituted.

        Everything else - the 1% risk budget, the 25% cap, the leverage - is the
        parent's. The wider stop gives a smaller position for the same risk, and
        that is the point: without it the wider arm would also be a bigger arm.
        """
        equity = self.wallets.get_total(self.config["stake_currency"])
        if equity is None or equity <= 0:
            return proposed_stake
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return proposed_stake
        import numpy as np
        atr = float(df["atr"].iloc[-1]) if "atr" in df else float("nan")
        price = float(df["close"].iloc[-1])
        if not np.isfinite(atr) or atr <= 0 or price <= 0:
            return proposed_stake
        lev = float(self.config.get("perp_leverage", 1.0))
        risk = float(self.config.get("risk_per_trade", self.risk_per_trade))
        notional = risk * equity / (self.stop_mult * (atr / price))
        stake = min(notional / lev, equity * float(
            self.config.get("max_stake_frac", self.max_stake_frac)))
        if min_stake:
            stake = max(stake, min_stake)
        return float(min(stake, max_stake))

    def custom_exit(self, pair: str, trade: Trade, current_time, current_rate: float,
                    current_profit: float, **kwargs) -> str | None:
        """Target stays 2R OF THE ENTRY-BAR STOP — the frozen rule generalised,
        not a second parameter moving at the same time."""
        stop_price = self._anchor_stop_price(pair, trade)
        risk = None
        if stop_price is not None:
            lev = trade.leverage or 1.0
            risk = stop_price - trade.open_rate * lev
        if risk is not None and risk > 0:
            lev = trade.leverage or 1.0
            target = trade.open_rate * lev - self.target_r * risk
            if current_rate <= target:
                return f"target_{self.target_r:g}R"
        held = ((current_time - trade.open_date_utc).total_seconds()
                / (self.timeframe_min * 60))
        if held >= self.time_stop_bars:
            return "time_stop"
        return None
