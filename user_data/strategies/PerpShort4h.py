# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
"""
PerpShort4h - the deployable version of the WIDE_PANEL frozen short rule.

WHAT THIS IS
------------
`ShortBreakout4h.py` is the CROSS-VALIDATION reference: it reproduced the shark
engine's 1,024 trades to within 0.3%. It has two declared approximations that
make it wrong as a *live* system:

  1. a FIXED -3.036% stoploss where the rule says "1.5 x the ATR at entry".
     The panel's 1.5xATR% ranges min 1.47% / median 3.61% / max 5.04%, so a
     fixed stop is 2.4x too wide on the calmest name and 1.7x too tight on the
     most volatile one. It is "the honest approximation" only in the sense that
     it is a documented approximation.
  2. `stake_amount` is fixed by the config, so every name carries the same
     dollar risk regardless of how far its ATR sits from the median.

This file fixes both, and adds the one risk control the panel result actually
demanded.

THE THREE FIXES
---------------

FIX 1 - a per-trade ATR stop that does not ratchet.
  The rule: stop = open + 1.5 x ATR(entry bar). Anchored to the ENTRY bar, so it
  never moves.

  WHY THE OBVIOUS CODE IS WRONG - this repo has now been bitten by this twice
  (WIDE_FT_MATRIX, LEVERAGE_MATRIX). freqtrade does not hold a stop PRICE. It
  holds a stop RATIO, and re-derives a price every bar
  (`LocalTrade.adjust_stop_loss`, trade_model.py:858-862):

      new_loss = current_price * (1 + abs(stoploss / leverage))

  So returning `atr / current_rate` - the intuitive "the stop is this many
  dollars away" - sets a stop that TRAVELS with price. On a losing short that
  tightens every bar and closes the trade within ~3 candles. That is the
  ratchet, and it produced a confident -22.44% / PF 0.67 that read like a
  falsification.

  The fix is to return the ratio whose DERIVED PRICE equals the anchor:

      stop_price S      = open_rate * (1 + 1.5*ATR/open_rate)
      required |stoploss| = S / current_rate - 1

  In backtesting, `current_rate` here is the candle's LOW for a short
  (interface.py:1573 passes `bound or current_rate`, and `bound = low` for
  shorts), and freqtrade only calls this while the stop is still above the
  candle's high (`dir_correct`, interface.py:1552-1556). So S > current_rate
  always, the abs() in adjust_stop_loss never flips the sign, and the derived
  price stays pinned at S on every subsequent bar. Verified empirically by
  `tools/perp_short/verify_stop.py`, which reads the trade export and asserts
  the realised stop distance equals 1.5 x ATR at entry.

  Note `leverage` multiplies the returned ratio, NOT the distance. At 1x that
  factor is 1; it is carried explicitly so the code stays correct at higher
  leverage instead of silently under-stopping (the exact §1 bug that turned a
  3.6% price stop into 0.18% at 20x).

FIX 2 - volatility-targeted sizing.
  Each trade risks `risk_per_trade` of equity measured in R, so the stake falls
  as ATR rises:

      stake = risk_per_trade * equity * leverage / (atr_stop * atr_pct)

  and is capped. The old fixed stake made the calmest names carry ~2.4x the
  intended risk.

FIX 3 - a portfolio risk cap, because 104 names is NOT diversification.
  WIDE_PANEL_RESULT.md §2 measured the thing that matters here: 7,914 trades land
  on only 2,222 distinct timestamps, 72% of trades share a timestamp with
  another trade, and regressing the cross-sectional mean of R on the market
  gives **beta = 1.000**. The book is one directional market bet wearing a
  volume filter. So the honest control is not a position COUNT, it is an
  aggregate risk budget: `risk_per_trade x max_open_trades` is the most the
  portfolio can lose if every stop is hit at once, and that product is what
  should be set, not the two numbers separately. It is printed in the runbook.

WHAT IS STILL NOT TRUE ABOUT THIS STRATEGY
-----------------------------------------
  * It is NOT a significant edge. The panel result is t_adjusted 1.8746 against
    a preregistered bar of 2.0 - a miss by 6.7%, not a pass.
  * It is NOT out-of-sample confirmed. The short leg was chosen after seeing the
    full sample, so the chronological splits are diagnostic.
  * The backtester has NO slippage and NO market-impact model
    (docs/backtesting.md:562 "All orders are filled at the requested price (no
    slippage)"; :571 "Stoploss exits happen exactly at stoploss price, even if
    low was lower"). Every number it prints is an UPPER bound. §1b of
    RESEARCH_STATE measures the real thing at 12.0 bps (calm) to 34.9 bps
    (COVID) round trip, and that is the number to size against.
  * Survivorship: the universe is "onboarded <= 2023-01-01 and still TRADING",
    so every figure is an upper bound. There is no public registry of delisted
    USD-M perps.

Run it with `--config user_data/config_perp_short.json`. See
`docs-myself/RUNBOOK-perp-short-4h.md`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, timeframe_to_prev_date


class PerpShort4h(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "4h"
    timeframe_min = 240
    can_short: bool = True

    # Frozen rule (PREREG_WIDE_PANEL_2026-09-27.md). Do not tune these.
    atr_period = 14
    atr_stop = 1.5
    target_r = 2.0
    rvol_period = 20
    rvol_threshold = 2.0
    breakout_period = 20
    time_stop_bars = 42
    vol_lookback = 42
    vol_med_window = 365

    # vol42(42) + a 365-bar median + breakout/rvol(20) => 420 is the true floor.
    startup_candle_count: int = 420

    # ---- FIX 1: backstop only, never the operative stop -----------------
    # The operative stop is 1.5 x ATR at entry, set per trade in custom_stoploss.
    # This class value must be WIDER than any stop custom_stoploss will ever
    # ask for, because freqtrade only lets a stop move in the tightening
    # direction (trade_model.py:886-893, "stop losses only walk up, never down").
    # Set it too tight and the ATR stop can never be applied. The panel's widest
    # 1.5xATR% is 5.04%; 30% is a wide backstop that liquidation (at 1x, ~100%)
    # cannot reach. 1 / 0.0504 = 19.8, so 0.30 leaves real headroom.
    stoploss = -0.30
    use_custom_stoploss = True

    trailing_stop = False
    process_only_new_candles = False

    # KEEP THIS True. IStrategy._get_exit_trade_type (interface.py) evaluates
    # custom_exit ONLY inside `if self.use_exit_signal:` - so setting it False
    # silently disables the 2R target AND the time stop, leaving the stoploss as
    # the only exit. An arm of the exit-family study returned 8 trades in 312
    # days this way and read as the best cell in the study. populate_exit_trend
    # therefore emits ZEROS, not a disabled flag.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    minimal_roi = {"0": 100}  # no ROI exits; the target is rule-based

    # FIX 2/3 sizing. Overridden per-config; these are the defaults the runbook
    # documents. risk_per_trade x max_open_trades is the portfolio risk budget.
    risk_per_trade = 0.01
    max_stake_frac = 0.25  # never more than a quarter of equity in one name

    # Backtest fills at the candle open, which is what the prereg specifies
    # ("filled at bar i open"). A limit order type in backtesting is priced
    # against the same candle, so market states the intent without ambiguity.
    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, **kwargs) -> float:
        """1x by default. Leverage is a risk DECISION, and the leverage matrix
        in RESEARCH_STATE.md already showed what raising it does: returns scale
        roughly linearly while drawdown scales worse, and fees equal the entire
        stop near 36x. Read that table before changing this."""
        return float(self.config.get("perp_leverage", 1.0))

    # ------------------------------------------------------------------
    # Frozen signal
    # ------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()

        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["atr"] = tr.ewm(
            alpha=1.0 / self.atr_period, adjust=False, min_periods=self.atr_period
        ).mean()

        vol = df["volume"].clip(lower=0.0)
        df["volume_sma"] = vol.rolling(
            self.rvol_period, min_periods=self.rvol_period
        ).mean()
        df["rvol"] = vol / df["volume_sma"].replace(0.0, np.nan)

        # Donchian EXCLUDES the current bar (shift(1)) so the level cannot
        # contain the bar that is being tested against it.
        df["prev_high"] = (
            df["high"].rolling(self.breakout_period, min_periods=self.breakout_period)
            .max()
            .shift(1)
        )
        df["prev_low"] = (
            df["low"].rolling(self.breakout_period, min_periods=self.breakout_period)
            .min()
            .shift(1)
        )

        # Low-volatility regime filter (Kurth et al. arXiv:2607.01550, preprint).
        # Time-series, per symbol, and the median is shifted(1) so the comparison
        # never uses the signal bar's own volatility in its own threshold.
        lr = np.log(df["close"]).diff()
        df["vol42"] = lr.rolling(self.vol_lookback, min_periods=self.vol_lookback).std()
        df["vol42_med"] = (
            df["vol42"].rolling(self.vol_med_window, min_periods=120).median().shift(1)
        )
        df["low_vol"] = (df["vol42"] < df["vol42_med"]).fillna(False)

        df["shark_short"] = (
            (df["rvol"] >= self.rvol_threshold)
            & (df["close"] < df["prev_low"])
            & df["low_vol"]
        )
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """SHORT ONLY. The long leg is net-negative in all 12 cells of the
        wide panel and all 3 cost regimes (WIDE_PANEL_RESULT.md §3) - but that
        split was made AFTER the fact, so it is reported as a preregistered
        short-leg line with its own frozen gates, not as a free choice."""
        dataframe.loc[dataframe["shark_short"], "enter_short"] = 1
        dataframe["enter_tag"] = np.where(dataframe["shark_short"], "shark_short", "")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Zeros on purpose - see the use_exit_signal comment in the class body."""
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    # ------------------------------------------------------------------
    # ATR frozen at the ENTRY bar
    # ------------------------------------------------------------------
    def entry_atr(self, pair: str, trade: Trade) -> float | None:
        """ATR at the bar the trade was opened on, NOT the current bar.

        This was a real defect once: the 2R target was measured with the LATEST
        ATR, so a trade opened at ATR 2% and closed at ATR 4% had its target
        silently doubled. That changes payoff geometry, holding time and the R
        distribution on every trade - the backtest was not measuring the frozen
        rule. Fixed 2026-09-27; it changes the baseline, and the baseline is
        what every later strategy is compared against.

        Uses freqtrade.exchange.timeframe_to_prev_date rather than
        Timestamp.floor(tf): on pandas 3 `floor("5m")` RAISES ('m' is no longer
        a frequency), and the failure is silent through strategy_safe_wrapper
        once the call sits inside custom_stoploss.

        THE FALLBACK IS THE MOST RECENT BAR, AND THAT IS NOT COSMETIC.
        ------------------------------------------------------
        On the ENTRY candle the analysed frame has not yet been extended to
        include that bar, so the lookup misses. Measured on this run:

            frame=[2023-09-22 .. 2023-12-24 20:00]  n_match=0  -> atr=None

        The first version of this function fell back to `df["atr"].iloc[0]` -
        the OLDEST bar, three months stale. It returned 304.28 where the entry
        bar's true ATR was 484.94, so the stop was set at +456.43 instead of
        +727.41. Because freqtrade only ever TIGHTENS a stop
        (trade_model.py:886-893), that too-tight stop could never be undone and
        persisted for the whole trade. 179 of 502 stop-outs were wrong, and the
        backtest printed a plausible equity curve throughout.

        The most recent bar is the correct fallback, not a lenient one: the
        entry fills at the OPEN of bar i, the decision was made at the close of
        bar i-1, and the frame is never ahead of the current candle - so on the
        entry candle `iloc[-1]` IS bar i-1, the last bar whose ATR was knowable
        at decision time. `tools/perp_short/verify_stop.py` is what caught this;
        reading the code would not have.
        """
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        try:
            entry_ts = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        except (AttributeError, TypeError, ValueError):
            return None
        at_entry = df.loc[df["date"] == entry_ts, "atr"]
        if len(at_entry):
            v = float(at_entry.iloc[-1])
        else:
            # see above: on the entry candle the frame ends one bar EARLIER, and
            # that bar is the causally correct one.
            v = float(df["atr"].iloc[-1])
        return v if np.isfinite(v) and v > 0 else None

    def _anchor_stop_price(self, pair: str, trade: Trade) -> float | None:
        """The frozen stop PRICE for this trade: open + 1.5 x ATR(entry)."""
        atr = self.entry_atr(pair, trade)
        if atr is None:
            return None
        lev = trade.leverage or 1.0
        # open_rate is the margin price (divided by leverage); the stop lives in
        # PRICE terms, so the distance is computed in price, not in margin.
        open_price = trade.open_rate * lev
        return open_price + self.atr_stop * atr

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool = False, **kwargs) -> float | None:
        """Return the RATIO whose derived price equals the anchored stop.

        See the module docstring for why `atr / current_rate` is wrong and this
        is not. Returns None when the anchor cannot be computed, which leaves
        the wide class backstop in place - deliberately loud, not silently tight.
        """
        if after_fill:
            return None
        stop_price = self._anchor_stop_price(pair, trade)
        if stop_price is None or not np.isfinite(stop_price):
            return None
        if not np.isfinite(current_rate) or current_rate <= 0:
            return None
        lev = trade.leverage or 1.0
        # new_loss = current * (1 + abs(sl / lev))  ->  sl = -(S/cur - 1) * lev
        # Guard the sign: freqtrade takes abs() inside adjust_stop_loss, so a
        # negative magnitude would be flipped into a stop ABOVE the anchor.
        ratio = (stop_price / current_rate) - 1.0
        if ratio <= 0:
            return None
        return -float(ratio * lev)

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | None:
        """2R from the ENTRY-bar ATR, else a 42-bar (~7 day) time stop."""
        stop_price = self._anchor_stop_price(pair, trade)
        risk = None
        if stop_price is not None:
            lev = trade.leverage or 1.0
            risk = stop_price - trade.open_rate * lev
        if risk is not None and risk > 0:
            lev = trade.leverage or 1.0
            target = trade.open_rate * lev - self.target_r * risk
            if current_rate <= target:
                return "target_2r"
        # SECONDS PER BAR = timeframe_min * 60 (4h -> 14400). Dividing by 240
        # (seconds per HOUR) reads one 4h bar as 60 bars and force-exits ~85%
        # of trades on their entry bar - a real bug that produced -31.72% and
        # read like a refutation of the shark result.
        held = ((current_time - trade.open_date_utc).total_seconds()
                / (self.timeframe_min * 60))
        if held >= self.time_stop_bars:
            return "time_stop"
        return None

    # ------------------------------------------------------------------
    # FIX 2: volatility-targeted sizing
    # ------------------------------------------------------------------
    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: float | None, max_stake: float,
                            entry_tag: str | None, side: str, **kwargs) -> float:
        """Risk `risk_per_trade` of equity per trade, measured in R.

        The stop is 1.5 x ATR, so a position of notional N loses 1.5*atr_pct*N
        at its stop. Setting that equal to risk_per_trade*equity gives

            N = risk_per_trade * equity / (1.5 * atr_pct)
        """
        equity = self.wallets.get_total(self.config["stake_currency"])
        if equity is None or equity <= 0:
            return proposed_stake
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return proposed_stake
        atr = float(df["atr"].iloc[-1]) if "atr" in df else float("nan")
        price = float(df["close"].iloc[-1])
        if not np.isfinite(atr) or atr <= 0 or price <= 0:
            return proposed_stake
        lev = float(self.config.get("perp_leverage", 1.0))
        risk_per_trade = float(self.config.get("risk_per_trade", self.risk_per_trade))
        atr_pct = atr / price
        notional = risk_per_trade * equity / (self.atr_stop * atr_pct)
        stake = notional / lev
        cap = equity * float(self.config.get("max_stake_frac", self.max_stake_frac))
        stake = min(stake, cap)
        # never below the exchange minimum, and never above what the engine
        # considers available for this slot
        if min_stake:
            stake = max(stake, min_stake)
        return float(min(stake, max_stake))
