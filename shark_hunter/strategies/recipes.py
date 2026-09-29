"""The SHARK-01..08 strategy family, the four baselines, and the ablation
machinery that makes "which signal actually carries the edge" answerable.

Every strategy is expressed as a :class:`StrategyRecipe` -- a set of boolean
feature switches layered on the same two primitives (relative volume and the
N-bar breakout).  The engine sees only the resulting boolean arrays, so an
ablation is literally the same recipe with one flag turned off.  Nothing else
changes: same exits, same sizing, same costs, same data.

The ladder (spec section 1)::

    SHARK-01  volume + breakout                     <- the baseline that matters
    SHARK-02  + VWAP
    SHARK-03  + CVD
    SHARK-04  + OBV
    SHARK-05  + OI
    SHARK-06  + CVD + OI
    SHARK-07  + liquidation (direction-specific)
    SHARK-08  + VWAP + CVD + (OI or liquidation) + optional funding filter
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from ..backtest.engine import (
    R_BO_ONLY, R_RANDOM, R_SHARK08, R_VOL_BO, R_VOL_BO_CVD, R_VOL_BO_CVD_OI,
    R_VOL_BO_LIQ, R_VOL_BO_OBV, R_VOL_BO_OI, R_VOL_BO_VWAP, R_VOL_ONLY,
    StrategySpec,
)


@dataclass(frozen=True)
class StrategyRecipe:
    name: str
    description: str
    rvol_threshold: float | None = 2.0     # None disables the volume filter
    use_breakout: bool = True
    breakout_period: int = 20
    vwap: bool = False
    cvd: bool = False
    cvd_lag: int = 5
    obv: bool = False
    oi: bool = False
    oi_lag: int = 3
    liquidation: bool = False
    liquidation_threshold: float = 3.0
    funding_filter: bool = False
    exit_mode: str = "atr_target"           # atr_target | vwap | cvd | breakout_level
    use_time_stop: bool = True
    random_seed: int | None = None
    # Baseline E: time-series momentum entry.  When set, the entry is a
    # lookback-return sign test instead of a level break, run through the
    # identical stop / target / cost machinery so that only the ENTRY RULE
    # differs from SHARK-01.  That is what makes it a control rather than
    # just another strategy.
    momentum_lookback: int | None = None

    def label(self) -> str:
        return self.name


# --------------------------------------------------------------------------
# The eight strategies
# --------------------------------------------------------------------------

STRATEGIES: dict[str, StrategyRecipe] = {
    "SHARK-01": StrategyRecipe(
        "SHARK-01", "Relative volume >= 2 and 20-bar breakout. The reference point.",
        exit_mode="atr_target"),
    "SHARK-02": StrategyRecipe(
        "SHARK-02", "SHARK-01 plus close on the correct side of UTC-daily VWAP.",
        vwap=True, exit_mode="vwap"),
    "SHARK-03": StrategyRecipe(
        "SHARK-03", "SHARK-01 plus CVD above its SMA and positive 5-bar CVD change.",
        cvd=True, exit_mode="cvd"),
    "SHARK-04": StrategyRecipe(
        "SHARK-04", "SHARK-01 plus OBV above its 20-bar SMA.",
        obv=True, exit_mode="atr_target"),
    "SHARK-05": StrategyRecipe(
        "SHARK-05", "SHARK-01 plus 15m open-interest change above zero.",
        oi=True, exit_mode="atr_target"),
    "SHARK-06": StrategyRecipe(
        "SHARK-06", "SHARK-01 plus positive 5-bar CVD change and rising 15m OI.",
        cvd=True, oi=True, exit_mode="atr_target"),
    "SHARK-07": StrategyRecipe(
        "SHARK-07", "SHARK-01 plus a same-side liquidation spike (cascade test).",
        liquidation=True, exit_mode="atr_target"),
    "SHARK-08": StrategyRecipe(
        "SHARK-08", "SHARK-01 plus VWAP, CVD momentum, and OI or liquidation; optional funding filter.",
        vwap=True, cvd=True, oi=True, liquidation=True, liquidation_threshold=2.0,
        funding_filter=True, exit_mode="atr_target"),
}

# Spec section 36.  These are what any claimed edge has to beat.
# BASELINE-A (buy-and-hold) is not a StrategySpec -- it has no stop, no
# target and no entry rule -- so it is evaluated directly in
# `analysis/benchmarks.py` and reported on its own terms.
# BASELINE-E is the control that matters most: SHARK-01 with the breakout
# replaced by a time-series momentum sign test, holding everything else
# (1 ATR stop, 2R target, same costs, same sizing) fixed.  If plain momentum
# explains the 4h result, the volume/breakout machinery is not doing the work.
BASELINES: dict[str, StrategyRecipe] = {
    "BASELINE-C-BREAKOUT": StrategyRecipe(
        "BASELINE-C-BREAKOUT", "Pure 20-bar breakout, no volume filter.",
        rvol_threshold=None, exit_mode="atr_target"),
    "BASELINE-D-RVOL": StrategyRecipe(
        "BASELINE-D-RVOL", "Pure relative-volume spike, no breakout filter.",
        rvol_threshold=2.0, use_breakout=False, exit_mode="atr_target"),
    "BASELINE-E-TSM": StrategyRecipe(
        "BASELINE-E-TSM", "Volume spike + 20-bar time-series momentum sign, same exits and costs.",
        use_breakout=False, momentum_lookback=20, exit_mode="atr_target"),
}

ALL_RECIPES: dict[str, StrategyRecipe] = {**STRATEGIES, **BASELINES}


# --------------------------------------------------------------------------
# Feature guards
# --------------------------------------------------------------------------

def _col_bool(df: pd.DataFrame, name: str) -> np.ndarray:
    if name not in df.columns:
        return np.zeros(len(df), dtype=bool)
    s = df[name]
    return s.fillna(False).to_numpy(dtype=bool)


def _col_num(df: pd.DataFrame, name: str) -> np.ndarray:
    if name not in df.columns:
        return np.full(len(df), np.nan)
    return pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)


def _has_data(df: pd.DataFrame, *cols: str) -> bool:
    """True when EVERY named column carries at least one usable observation.

    A strategy that depends on an unavailable feed must be reported as
    BLOCKED, not silently run on all-NaN columns (which would degenerate into
    'always false' and look like a strategy with no edge rather than one that
    was never tested).

    The check covers all columns, not just the first.  An earlier version
    returned from inside the loop, so only ``cols[0]`` was ever examined and
    the answer depended on argument order.
    """
    if not cols:
        return False
    for c in cols:
        if c not in df.columns:
            return False
        if df[c].isna().all():
            return False
    return True


def unavailable_dependencies(df: pd.DataFrame, recipe: StrategyRecipe) -> list[str]:
    missing: list[str] = []
    if recipe.oi and not _has_data(df, "open_interest"):
        missing.append("open_interest")
    if recipe.funding_filter and not _has_data(df, "funding_rate"):
        missing.append("funding_rate")
    if recipe.liquidation and not _has_data(df, "liquidation_ratio"):
        missing.append("liquidation")
    if recipe.cvd and not _has_data(df, "taker_buy_volume"):
        missing.append("taker_buy_volume")
    if recipe.vwap and not _has_data(df, "vwap"):
        missing.append("vwap")
    return missing


# --------------------------------------------------------------------------
# Spec builder
# --------------------------------------------------------------------------

def build_spec(df: pd.DataFrame, recipe: StrategyRecipe, *,
               atr_stop: float = 1.0,
               r_multiple: float = 2.0,
               time_stop_bars: int = 24,
               cooldown_bars: int = 3,
               trailing_atr: float | None = None,
               rvol_threshold: float | None = -1.0,
               oi_lag: int | None = None) -> StrategySpec:
    """Turn a recipe into the boolean arrays the engine consumes.

    ``rvol_threshold=-1.0`` means "use the recipe's own threshold"; passing a
    number is how the parameter sweep overrides it without cloning the recipe.
    """
    n = len(df)
    thr = recipe.rvol_threshold if rvol_threshold < 0 else rvol_threshold

    rvol = _col_num(df, "rvol")
    close = _col_num(df, "close")
    prev_high = _col_num(df, "prev_high")
    prev_low = _col_num(df, "prev_low")
    vwap = _col_num(df, "vwap")
    cvd_sma = _col_num(df, "cvd_sma")
    obv_sma = _col_num(df, "obv_sma")
    liq_long = _col_num(df, "long_liquidation_ratio")
    liq_short = _col_num(df, "short_liquidation_ratio")
    liq_total = _col_num(df, "liquidation_ratio")
    fund_z = _col_num(df, "funding_zscore")

    lag = oi_lag if oi_lag is not None else recipe.oi_lag
    oi_col = f"oi_change_{lag}"
    oi_chg = _col_num(df, oi_col)
    if np.isnan(oi_chg).all() and f"oi_change_{recipe.oi_lag}" in df.columns:
        oi_chg = _col_num(df, f"oi_change_{recipe.oi_lag}")
    cvd_delta = _col_num(df, f"cvd_delta_{recipe.cvd_lag}")

    # ---- base conditions --------------------------------------------------
    # Start from all-True and AND each filter in.  Starting from all-False
    # would silently produce an empty signal set for every strategy.
    base = np.ones(n, dtype=bool)
    if recipe.rvol_threshold is not None or rvol_threshold >= 0:
        base &= ~np.isnan(rvol) & (rvol >= thr)
    if recipe.use_breakout:
        base &= (close > prev_high) | (close < prev_low)

    # Direction.  With a breakout filter the level break itself decides the
    # side; without one (Baseline D) the bar's own body does, so that
    # "volume spike without breakout" is genuinely a different signal rather
    # than SHARK-01 with a flag flipped.
    if recipe.momentum_lookback is not None:
        # Baseline E: the sign of the trailing return decides the side, and
        # the volume spike is still required -- this is deliberately
        # SHARK-01 with the *breakout* replaced by momentum, so the two
        # isolate which half of SHARK-01 carries the information.
        close_s = pd.Series(close, index=df.index)
        mom = (close_s / close_s.shift(recipe.momentum_lookback) - 1.0).to_numpy()
        bo_long = base & ~np.isnan(mom) & (mom > 0)
        bo_short = base & ~np.isnan(mom) & (mom < 0)
    elif recipe.use_breakout:
        bo_long = base & (close > prev_high)
        bo_short = base & (close < prev_low)
    else:
        open_ = _col_num(df, "open")
        bo_long = base & (close > open_)
        bo_short = base & (close < open_)

    above_vwap = close > vwap
    below_vwap = close < vwap
    # Element-wise guards only: `and` on a numpy array raises, so the NaN
    # suppression has to happen inside the arithmetic.
    cvd_level = _col_num(df, "cvd")
    cvd_bull = np.where(np.isnan(cvd_sma), False, cvd_level > cvd_sma)
    cvd_bear = np.where(np.isnan(cvd_sma), False, cvd_level < cvd_sma)
    cvd_dn = np.where(np.isnan(cvd_delta), False, cvd_delta > 0)
    cvd_up = np.where(np.isnan(cvd_delta), False, cvd_delta < 0)
    obv_level = _col_num(df, "obv")
    obv_bull = np.where(np.isnan(obv_sma), False, obv_level > obv_sma)
    obv_bear = np.where(np.isnan(obv_sma), False, obv_level < obv_sma)
    oi_up = np.where(np.isnan(oi_chg), False, oi_chg > 0)

    # ---- entry conditions per strategy ------------------------------------
    if recipe.random_seed is not None:
        rng = np.random.default_rng(recipe.random_seed)
        long_entry = _random_entries(n, rng)
        short_entry = _random_entries(n, rng)
        long_reason = np.full(n, R_RANDOM, dtype=int)
        short_reason = np.full(n, R_RANDOM, dtype=int)
    else:
        long_entry = bo_long.copy()
        short_entry = bo_short.copy()
        long_reason = np.full(n, R_VOL_BO, dtype=int)
        short_reason = np.full(n, R_VOL_BO, dtype=int)

        if recipe.vwap:
            long_entry &= above_vwap
            short_entry &= below_vwap
            long_reason = np.where(long_entry, R_VOL_BO_VWAP, long_reason)
            short_reason = np.where(short_entry, R_VOL_BO_VWAP, short_reason)

        if recipe.cvd:
            long_entry &= cvd_bull & cvd_dn
            short_entry &= cvd_bear & cvd_up
            long_reason = np.where(long_entry, R_VOL_BO_CVD, long_reason)
            short_reason = np.where(short_entry, R_VOL_BO_CVD, short_reason)

        if recipe.obv:
            long_entry &= obv_bull
            short_entry &= obv_bear
            long_reason = np.where(long_entry, R_VOL_BO_OBV, long_reason)
            short_reason = np.where(short_entry, R_VOL_BO_OBV, short_reason)

        if recipe.oi:
            long_entry &= oi_up
            short_entry &= oi_up          # spec 20: OI > 0 on BOTH sides, deliberately
            long_reason = np.where(long_entry, R_VOL_BO_OI, long_reason)
            short_reason = np.where(short_entry, R_VOL_BO_OI, short_reason)

        if recipe.liquidation:
            # Spec 22/23: a same-side liquidation spike, not "liquidations are
            # a buy".  Longs want shorts liquidated, shorts want longs.
            if recipe.name == "SHARK-08":
                # SHARK-08 accepts EITHER rising OI or a liquidation spike.
                liq_ok_long = (liq_short >= recipe.liquidation_threshold) | oi_up
                liq_ok_short = (liq_long >= recipe.liquidation_threshold) | oi_up
            else:
                liq_ok_long = liq_short >= recipe.liquidation_threshold
                liq_ok_short = liq_long >= recipe.liquidation_threshold
            long_entry &= liq_ok_long
            short_entry &= liq_ok_short
            long_reason = np.where(long_entry, R_VOL_BO_LIQ, long_reason)
            short_reason = np.where(short_entry, R_VOL_BO_LIQ, short_reason)

        if recipe.funding_filter:
            # Only removes trades; it never creates one.
            long_entry &= np.where(np.isnan(fund_z), True, fund_z <= 2.0)
            short_entry &= np.where(np.isnan(fund_z), True, fund_z >= -2.0)
            long_reason = np.where(long_entry, R_SHARK08, long_reason)
            short_reason = np.where(short_entry, R_SHARK08, short_reason)

        if not recipe.use_breakout:
            long_reason = np.where(long_entry, R_VOL_ONLY, long_reason)
            short_reason = np.where(short_entry, R_VOL_ONLY, short_reason)
        if recipe.rvol_threshold is None:
            long_reason = np.where(long_entry, R_BO_ONLY, long_reason)
            short_reason = np.where(short_entry, R_BO_ONLY, short_reason)

    # ---- exit conditions --------------------------------------------------
    use_signal_exit = recipe.exit_mode in ("vwap", "cvd", "breakout_level")
    if recipe.exit_mode == "vwap":
        long_exit = below_vwap
        short_exit = above_vwap
    elif recipe.exit_mode == "cvd":
        long_exit = cvd_bear
        short_exit = cvd_bull
    elif recipe.exit_mode == "breakout_level":
        long_exit = close < prev_high
        short_exit = close > prev_low
    else:
        long_exit = np.zeros(n, dtype=bool)
        short_exit = np.zeros(n, dtype=bool)

    return StrategySpec(
        name=recipe.name,
        long_entry=long_entry, short_entry=short_entry,
        long_exit=long_exit, short_exit=short_exit,
        long_reason=long_reason, short_reason=short_reason,
        atr_stop=atr_stop, r_multiple=r_multiple,
        time_stop_bars=time_stop_bars if recipe.use_time_stop else 10**9,
        cooldown_bars=cooldown_bars,
        trailing_atr=trailing_atr,
        use_signal_exit=use_signal_exit,
    )


def _random_entries(n: int, rng: np.random.Generator) -> np.ndarray:
    """Baseline B: random entry, matched count per bar to SHARK-01's rate."""
    target = 0.01
    return rng.random(n) < target


def ablation_variants(name: str) -> list[tuple[str, StrategyRecipe]]:
    """Spec 37: for a composite strategy, the 'full minus one leg' family."""
    base = STRATEGIES[name]
    legs = ["Volume", "CVD", "OI", "VWAP", "OBV", "Liquidation", "Funding"]
    out: list[tuple[str, StrategyRecipe]] = []
    for leg in legs:
        r = replace(base)
        if leg == "Volume" and r.rvol_threshold is not None:
            r = replace(r, rvol_threshold=None, name=f"{name}-noVolume")
        elif leg == "CVD" and r.cvd:
            r = replace(r, cvd=False, name=f"{name}-noCVD")
        elif leg == "OI" and r.oi:
            r = replace(r, oi=False, name=f"{name}-noOI")
        elif leg == "VWAP" and r.vwap:
            r = replace(r, vwap=False, name=f"{name}-noVWAP")
        elif leg == "OBV" and r.obv:
            r = replace(r, obv=False, name=f"{name}-noOBV")
        elif leg == "Liquidation" and r.liquidation:
            r = replace(r, liquidation=False, name=f"{name}-noLiq")
        elif leg == "Funding" and r.funding_filter:
            r = replace(r, funding_filter=False, name=f"{name}-noFunding")
        else:
            continue
        out.append((leg, r))
    return out
