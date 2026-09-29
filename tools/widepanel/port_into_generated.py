"""Port the frozen rule into the freqtrade-GENERATED strategy file.

Keeps everything `freqtrade new-strategy` produced (imports, class header,
informative_pairs, hyperopt plumbing, plot_config) and replaces only
`populate_indicators` plus the tail methods. Done by line surgery because the
template's exact whitespace defeated repeated literal edits.
"""

from __future__ import annotations

from pathlib import Path

P = Path("user_data/strategies/ShortBreakout4h.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

# keep everything up to and including `def informative_pairs(...)` block and the
# hyperopt decorators, i.e. cut at the line that starts populate_indicators
cut = next(i for i, l in enumerate(lines) if l.lstrip().startswith("def populate_indicators"))
head = lines[:cut]

# drop a dangling @... decorator immediately above the cut, if any
while head and head[-1].lstrip().startswith("@"):
    head.pop()

BODY = '''
    # ------------------------------------------------------------------
    # Frozen rule (docs-myself/PREREG_WIDE_PANEL_2026-09-27.md)
    # ------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """ATR(14), relative volume(20), 20-bar Donchian, and the frozen
        low-volatility regime filter.

        The breakout levels EXCLUDE the current bar (shift(1)), and the
        volatility median is shifted(1), so nothing here reads the bar it is
        deciding. The relative-volume average INCLUDES the current bar, which
        is causal because that bar's volume is complete at its close; this
        matches the shark engine's convention exactly.
        """
        df = dataframe.copy()

        prev_close = df["close"].shift(1)
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        df["atr"] = tr.ewm(alpha=1.0 / 14.0, adjust=False,
                           min_periods=14).mean()

        vol = df["volume"].clip(lower=0.0)
        df["volume_sma"] = vol.rolling(self.rvol_period,
                                       min_periods=self.rvol_period).mean()
        df["rvol"] = vol / df["volume_sma"].replace(0.0, np.nan)

        df["prev_high"] = df["high"].rolling(self.breakout_period,
                                             min_periods=self.breakout_period
                                             ).max().shift(1)
        df["prev_low"] = df["low"].rolling(self.breakout_period,
                                           min_periods=self.breakout_period
                                           ).min().shift(1)

        # low-vol regime filter: trailing 42-bar vol below its own 365-bar median
        lr = np.log(df["close"]).diff()
        df["vol42"] = lr.rolling(self.vol_lookback,
                                 min_periods=self.vol_lookback).std()
        df["vol42_med"] = df["vol42"].rolling(
            self.vol_med_window, min_periods=120).median().shift(1)
        df["low_vol"] = (df["vol42"] < df["vol42_med"]).fillna(False)

        df["shark_short"] = ((df["rvol"] >= self.rvol_threshold)
                             & (df["close"] < df["prev_low"])
                             & df["low_vol"])
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict
                             ) -> DataFrame:
        """SHORT only. The long leg is net-negative in every cell and every
        cost regime of the wide-panel run.

        Conditions are evaluated on the signal candle's close; freqtrade fills
        at the next candle's open, matching the shark engine's convention.
        """
        dataframe.loc[dataframe["shark_short"],
                       ["enter_long", "enter_short"]] = (0, 1)
        dataframe.loc[~dataframe["shark_short"],
                       ["enter_long", "enter_short"]] = (0, 0)
        dataframe["enter_tag"] = np.where(dataframe["shark_short"],
                                          "shark_short", "")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict
                            ) -> DataFrame:
        """No signal exit: the 2R target and the time stop are rule-based."""
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def custom_exit(self, pair: str, trade, current_time, current_rate: float,
                    current_profit: float, **kwargs) -> str | None:
        """2R target, else a 42-bar (~7 day) time stop."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(df) < 2:
            return None
        atr = df["atr"].iloc[-1]
        if np.isfinite(atr) and atr > 0:
            target = trade.open_rate - self.target_r * self.atr_stop * atr
            if current_rate <= target:
                return "target_2r"
        # SECONDS PER BAR = timeframe_min * 60 (4h -> 14400). Dividing by 240
        # (seconds per HOUR) reads one 4h bar as 60 bars and force-exits ~85%
        # of trades on their entry bar.
        held = ((current_time - trade.open_date_utc).total_seconds()
                / (self.timeframe_min * 60))
        if held >= self.time_stop_bars:
            return "time_stop"
        return None
'''

P.write_text("".join(head) + BODY, encoding="utf-8")
print(f"kept {len(head)} generated lines, replaced from line {cut + 1}")
