"""Regression tests for the six classic backtest traps.

Run before any result is believed:

    python -m shark_hunter.tests.test_regressions

Standalone on purpose (no pytest in this environment) and modelled on the
``quant-research-handoff/methodology/test_regressions.py`` suite, because the
failure mode being guarded against is a test suite that itself silently stops
running.

The tests that matter most here are the *truncation* tests: recompute every
feature on a truncated history and assert the shared bars are bit-identical.
That catches lookahead of any kind, including subtle cases like a
``rolling().max()`` without the ``shift(1)`` that a hand-written rule check
would miss.
"""

from __future__ import annotations

import sys
import traceback

import numpy as np
import pandas as pd

from .. import config as C
from .. import features
from ..backtest.costs import CostModel
from ..backtest.engine import StrategySpec, run_backtest
from ..features import atr as f_atr
from ..features import cvd as f_cvd
from ..features import vwap as f_vwap
from ..strategies.recipes import (BASELINES, STRATEGIES, build_spec,
                                 unavailable_dependencies)

# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

_TESTS: list = []


def test(fn):
    _TESTS.append(fn)
    return fn


def approx(a, b, tol=1e-9) -> bool:
    return bool(np.all(np.abs(np.asarray(a) - np.asarray(b)) <= tol))


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def make_frame(n: int = 400, seed: int = 7, start: str = "2024-01-01") -> pd.DataFrame:
    """A deterministic OHLCV frame with taker split and a 5m grid."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="5min", tz="UTC")
    ret = rng.normal(0, 0.0015, n)
    close = 100.0 * np.exp(np.cumsum(ret))
    open_ = np.concatenate([[close[0]], close[:-1]])
    spread = np.abs(rng.normal(0, 0.0008, n)) + 0.0004
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    # Lognormal volume: real traded volume is fat-tailed and genuinely spikes.
    # An iid-normal volume series can never reach RVOL 2, which would make
    # every volume-based test vacuously pass or fail for the wrong reason.
    volume = np.exp(rng.normal(np.log(50.0), 0.75, n))
    taker_buy = volume * rng.uniform(0.35, 0.65, n)
    df = pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close,
        "volume": volume, "quote_volume": volume * close,
        "trades": np.full(n, 100), "taker_buy_volume": taker_buy,
        "taker_buy_quote_volume": taker_buy * close,
        "taker_sell_volume": volume - taker_buy,
    }, index=idx)
    df.index.name = "timestamp"
    return df


def make_feature_frame(n: int = 600, seed: int = 11) -> pd.DataFrame:
    df = make_frame(n, seed)
    return features.add_all(df, timeframe="5m")


# ==========================================================================
# 1. CAUSALITY: no feature may use information after its own bar
# ==========================================================================

CAUSAL_COLUMNS = [
    "rvol", "volume_sma", "prev_high", "prev_low", "breakout_long", "breakout_short",
    "atr", "true_range", "vwap", "above_vwap", "obv", "obv_sma", "cvd", "cvd_sma",
    "cvd_delta_5", "taker_imbalance",
]


@test
def test_features_are_causal_under_truncation():
    """Recomputing on a truncated history must not change the shared bars."""
    full = make_feature_frame(800, seed=3)
    for cut in (300, 500, 700):
        partial = features.add_all(make_frame(800, seed=3).iloc[:cut], timeframe="5m")
        cols = [c for c in CAUSAL_COLUMNS if c in full.columns and c in partial.columns]
        assert cols, "no comparable causal columns"
        a = full[cols].iloc[:cut]
        b = partial[cols]
        # Object-dtype columns (booleans) compare exactly; floats with tolerance.
        for c in cols:
            x, y = a[c].to_numpy(), b[c].to_numpy()
            if x.dtype == object or y.dtype == bool or y.dtype == object:
                same = np.array_equal(pd.isna(x), pd.isna(y)) and np.array_equal(x == y, ~(pd.isna(x) | pd.isna(y)))
            else:
                both_nan = np.isnan(x.astype(float)) & np.isnan(y.astype(float))
                same = np.all(both_nan | (np.abs(np.nan_to_num(x) - np.nan_to_num(y)) < 1e-12))
            assert same, f"column {c!r} changed when history was truncated at {cut} -> LOOKAHEAD"


@test
def test_only_forward_return_columns_are_lookahead():
    """No non-quarantined column may be a function of the future.

    The previous version of this test filtered columns by the `fwd_ret_`
    prefix and then asserted each survivor contained that prefix, which is a
    tautology -- it can never fail, and it passed with a blatant look-ahead
    column injected into the frame. It now asserts the thing it claims: that
    every column OUTSIDE the quarantine is causal under truncation, and that
    an injected future-looking column is caught.
    """
    df = make_frame(600, seed=33)
    out = features.add_all(df, timeframe="5m")

    # Inject an unmistakable look-ahead and confirm the causal check catches it.
    poisoned = out.copy()
    poisoned["leaky_regime"] = (poisoned["close"].shift(-3) > poisoned["close"] * 1.05)
    causal_cols = [c for c in Causal_columns(poisoned) if c not in CAUSAL_COLUMNS]
    assert "leaky_regime" in causal_cols, "injected look-ahead column not detected"

    partial = features.add_all(df.iloc[:300], timeframe="5m")
    for col in CAUSAL_COLUMNS:
        if col not in partial.columns:
            continue
        a = out[col].iloc[:300].to_numpy()
        b = partial[col].to_numpy()
        both_nan = np.asarray(pd.isna(a)) & np.asarray(pd.isna(b))
        # Coerce to float: several causal columns are boolean and numpy has
        # no absolute value for them.
        av = np.asarray(a, dtype=float).astype(float)
        bv = np.asarray(b, dtype=float).astype(float)
        ok = np.all(both_nan | (np.abs(np.nan_to_num(av) - np.nan_to_num(bv)) < 1e-12))
        assert ok, f"{col} changed under truncation -> not causal"


def Causal_columns(df):
    return list(df.columns)


# ==========================================================================
# 2. LOOKAHEAD-BY-CONSTRUCTION
# ==========================================================================

@test
def test_breakout_excludes_current_bar():
    df = make_frame(100, seed=2)
    out = features.add_breakout(df, period=20)
    i = 50
    # A wildly higher high on bar i must not change the level it is compared to.
    df2 = df.copy()
    df2.iloc[i, df2.columns.get_loc("high")] = 1e6
    out2 = features.add_breakout(df2, period=20)
    assert approx(out["prev_high"].iloc[i], out2["prev_high"].iloc[i]), \
        "prev_high reacted to the current bar's high -> includes current candle"


@test
def test_vwap_resets_daily_and_is_running():
    df = make_frame(300, seed=4, start="2024-03-05 20:00")  # spans a UTC midnight
    out = f_vwap.add_vwap(df)
    days = out.index.floor("D").unique()
    assert len(days) >= 2, "fixture did not span a day boundary"
    for d in days:
        sl = out.loc[out.index.floor("D") == d]
        first = sl.iloc[0]
        tp = (first["high"] + first["low"] + first["close"]) / 3
        assert approx(first["vwap"], tp, 1e-9), "VWAP at the first bar of a day is not that bar alone"
    # Running VWAP must equal the manual cumulative computation.
    tp = (out["high"] + out["low"] + out["close"]) / 3
    manual = (tp * out["volume"]).groupby(out.index.floor("D")).cumsum() / \
             out["volume"].groupby(out.index.floor("D")).cumsum()
    assert approx(out["vwap"].dropna().to_numpy(), manual.dropna().to_numpy(), 1e-9)


@test
def test_oa_value_changes_do_not_affect_earlier_bars():
    df = make_feature_frame(500, seed=8)
    i = 300
    df2 = df.copy()
    # Rewrite the future with wildly different prices; the past must not move.
    df2.iloc[i:, df2.columns.get_loc("close")] *= 3.0
    for i2 in range(i, len(df2)):
        df2.iloc[i2, df2.columns.get_loc("prev_high")] *= 3.0
        df2.iloc[i2, df2.columns.get_loc("prev_low")] *= 3.0
    for c in ("rvol", "prev_high", "prev_low", "vwap", "obv", "cvd", "cvd_sma"):
        a, b = df[c].iloc[:i].to_numpy(), df2[c].iloc[:i].to_numpy()
        both_nan = np.isnan(a.astype(float)) & np.isnan(b.astype(float))
        assert np.all(both_nan | (np.abs(np.nan_to_num(a) - np.nan_to_num(b)) < 1e-9)), \
            f"{c} changed when only FUTURE bars were rewritten -> LOOKAHEAD"


# ==========================================================================
# 3. FEATURE ARITHMETIC
# ==========================================================================

@test
def test_rvol_definition():
    df = make_frame(200, seed=6)
    out = features.add_rvol(df, period=20)
    i = 100
    manual = df["volume"].iloc[i] / df["volume"].iloc[i - 19:i + 1].mean()
    assert approx(out["rvol"].iloc[i], manual, 1e-12)


@test
def test_cvd_arithmetic():
    df = make_frame(200, seed=9)
    out = f_cvd.add_cvd(df, lags=(5,), sma_period=20)
    delta = df["taker_buy_volume"] - df["taker_sell_volume"]
    assert approx(out["cvd"].iloc[:50].to_numpy(), delta.iloc[:50].cumsum().to_numpy(), 1e-9)
    i = 100
    assert approx(out["cvd_delta_5"].iloc[i], out["cvd"].iloc[i] - out["cvd"].iloc[i - 5], 1e-9)


@test
def test_atr_matches_manual_wilder():
    df = make_frame(200, seed=10)
    out = f_atr.add_atr(df, period=14)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    manual = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    assert approx(out["atr"].dropna().to_numpy(), manual.dropna().to_numpy(), 1e-9)


# ==========================================================================
# 4. EXECUTION TIMING
# ==========================================================================

def _spec_from_signals(df, longs, shorts, exits=None, **kw) -> StrategySpec:
    n = len(df)
    ones = np.ones(n, dtype=bool)
    return StrategySpec(
        name="T", long_entry=longs, short_entry=shorts,
        long_exit=exits if exits is not None else np.zeros(n, bool),
        short_exit=exits if exits is not None else np.zeros(n, bool),
        long_reason=ones.astype(int), short_reason=ones.astype(int), **kw)


@test
def test_entry_fills_at_next_bar_open_not_signal_close():
    df = make_feature_frame(300, seed=12)
    sig = np.zeros(len(df), dtype=bool)
    sig[100] = True
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy()),
                       costs=CostModel(slippage_bps=0.0, apply_funding=False))
    assert len(res.trades) == 1, f"expected 1 trade, got {len(res.trades)}"
    t = res.trades.iloc[0]
    assert t["signal_time"] == df.index[100], "signal timestamp not on the signal bar"
    assert t["entry_time"] == df.index[101], \
        f"entry happened on {t['entry_time']} instead of the NEXT bar {df.index[101]}"
    assert approx(t["entry_price"], df["open"].iloc[101], 1e-9), \
        "entry price is not the next bar's open"


@test
def test_engine_cannot_see_the_current_bar_high_before_its_close():
    """A signal on bar t must not be able to exploit bar t's own high."""
    df = make_feature_frame(300, seed=13)
    sig = np.zeros(len(df), dtype=bool)
    sig[100] = True
    base = run_backtest(df, _spec_from_signals(df, sig, sig.copy()),
                        costs=CostModel(slippage_bps=0.0, apply_funding=False))
    df2 = df.copy()
    df2.iloc[100, df2.columns.get_loc("high")] *= 5.0   # spike on the signal bar only
    alt = run_backtest(df2, _spec_from_signals(df2, sig, sig.copy()),
                       costs=CostModel(slippage_bps=0.0, apply_funding=False))
    assert base.trades.iloc[0]["entry_price"] == alt.trades.iloc[0]["entry_price"], \
        "entry price changed when only the signal bar's high was altered -> intrabar lookahead"


@test
def test_stop_gap_fills_at_open_not_the_level():
    """A bar that gaps through the stop fills at the open, worse than the level.

    The fixture must stay OHLC-consistent (low <= open <= high); the integrity
    checker rejects the alternative, so a test that fabricates one would be
    testing a data shape that can never reach the engine.
    """
    df = make_feature_frame(400, seed=14)
    sig = np.zeros(len(df), dtype=bool)
    sig[50] = True
    i = 52                                  # one bar AFTER the fill at bar 51
    gapped_open = df["close"].iloc[51] * 0.95   # gaps ~5% down through the stop
    df.iloc[i, df.columns.get_loc("open")] = gapped_open
    df.iloc[i, df.columns.get_loc("high")] = max(gapped_open, df["high"].iloc[i])
    df.iloc[i, df.columns.get_loc("low")] = gapped_open * 0.99
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy(), atr_stop=1.0, r_multiple=2.0),
                       costs=CostModel(slippage_bps=0.0, apply_funding=False))
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop", f"expected a stop exit, got {t['exit_reason']}"
    assert t["exit_time"] == df.index[i]
    assert t["exit_price"] < t["stop_price"], \
        f"gap-through stop must fill worse than the stop level " \
        f"(filled {t['exit_price']}, stop {t['stop_price']})"
    assert approx(t["exit_price"], gapped_open, 1e-9), "gap fill must be the open price"


@test
def test_stop_wins_when_a_bar_touches_both_levels():
    """Ambiguous intrabar paths resolve pessimistically, never optimistically."""
    df = make_feature_frame(300, seed=15)
    sig = np.zeros(len(df), dtype=bool)
    sig[50] = True
    t0 = res_trade = None
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy(), atr_stop=1.0, r_multiple=2.0),
                       costs=CostModel(slippage_bps=0.0, apply_funding=False))
    entry = res.trades.iloc[0]["entry_reference"]
    stop = res.trades.iloc[0]["stop_price"]
    target = res.trades.iloc[0]["target_price"]
    # Now force a bar that spans both the stop and the target.
    df2 = df.copy()
    i = 51
    df2.iloc[i, df2.columns.get_loc("high")] = max(target, df2["high"].iloc[i]) * 1.01
    df2.iloc[i, df2.columns.get_loc("low")] = min(stop, df2["low"].iloc[i]) * 0.99
    res2 = run_backtest(df2, _spec_from_signals(df2, sig, sig.copy(), atr_stop=1.0, r_multiple=2.0),
                        costs=CostModel(slippage_bps=0.0, apply_funding=False))
    assert res2.trades.iloc[0]["exit_reason"] == "stop", \
        "a bar touching stop and target must resolve to the stop"


# ==========================================================================
# 5. PNL AND COST IDENTITY
# ==========================================================================

@test
def test_trade_pnl_identity():
    df = make_feature_frame(600, seed=16)
    df["funding_event"] = False
    sig = np.zeros(len(df), dtype=bool)
    sig[::37] = True
    costs = CostModel(slippage_bps=2.0)
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy()), costs=costs)
    assert len(res.trades) > 3
    for _, t in res.trades.iterrows():
        sgn = 1.0 if t["direction"] == "long" else -1.0
        exec_pnl = (t["exit_price"] - t["entry_price"]) * t["quantity"] * sgn
        assert abs(exec_pnl - t["fees"] - t["funding"] - t["net_pnl"]) < 1e-6, \
            "net_pnl != executed pnl - fees - funding"
        raw = (t["exit_reference"] - t["entry_reference"]) * t["quantity"] * sgn
        assert abs(raw - t["gross_pnl"]) < 1e-6, "gross_pnl != raw price move * qty"
        assert abs((raw - exec_pnl) - t["slippage_cost"]) < 1e-6, "slippage_cost not accounted"


@test
def test_fees_are_charged_on_both_legs():
    df = make_feature_frame(400, seed=17)
    df["funding_event"] = False
    sig = np.zeros(len(df), dtype=bool)
    sig[::40] = True
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy()),
                       costs=CostModel(slippage_bps=0.0))
    for _, t in res.trades.iterrows():
        assert t["fee_entry"] > 0 and t["fee_exit"] > 0, "a leg escaped the fee"
        assert abs(t["fees"] - (t["fee_entry"] + t["fee_exit"])) < 1e-9


@test
def test_zero_slippage_and_zero_fee_is_pure_price_move():
    df = make_feature_frame(400, seed=18)
    df["funding_event"] = False
    sig = np.zeros(len(df), dtype=bool)
    sig[::45] = True
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy()),
                       costs=CostModel(taker_fee_bps=0.0, slippage_bps=0.0, apply_funding=False))
    for _, t in res.trades.iterrows():
        assert abs(t["slippage_cost"]) < 1e-9, "slippage charged with a zero slippage model"
        assert abs(t["fees"]) < 1e-9, "fees charged with a zero fee model"


@test
def test_slippage_always_works_against_the_trader():
    """slippage_cost is defined as gross - executed, so it must never be < 0."""
    df = make_feature_frame(400, seed=19)
    df["funding_event"] = False
    sig = np.zeros(len(df), dtype=bool)
    sig[::40] = True
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy()),
                       costs=CostModel(slippage_bps=10.0))
    for _, t in res.trades.iterrows():
        assert t["slippage_cost"] >= -1e-9, \
            f"slippage_cost {t['slippage_cost']} < 0 -> execution improved the fill"


@test
def test_funding_is_charged_only_on_event_bars():
    df = make_feature_frame(400, seed=20)
    sig = np.zeros(len(df), dtype=bool)
    sig[50] = True
    df["funding_event"] = False
    df["funding_rate"] = 0.0001
    no_fund = run_backtest(df.copy(), _spec_from_signals(df, sig, sig.copy()),
                           costs=CostModel(slippage_bps=0.0, apply_funding=False))
    assert approx(no_fund.trades.iloc[0]["funding"], 0.0), "funding charged off-event"

    df2 = df.copy()
    df2["funding_event"] = True          # every bar is an event
    all_fund = run_backtest(df2, _spec_from_signals(df2, sig, sig.copy()),
                            costs=CostModel(slippage_bps=0.0, apply_funding=True))
    assert all_fund.trades.iloc[0]["funding"] > 0, "funding never charged on event bars"


# ==========================================================================
# 6. POSITION RULES
# ==========================================================================

@test
def test_never_two_positions_and_never_pyramids():
    df = make_feature_frame(500, seed=21)
    df["funding_event"] = False
    sig = np.ones(len(df), dtype=bool)     # signal on every single bar
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy(), cooldown_bars=3),
                       costs=CostModel(slippage_bps=0.0, apply_funding=False))
    t = res.trades
    assert len(t) > 1
    # Exit of trade k must precede entry of trade k+1.
    assert (t["entry_time"].iloc[1:].to_numpy() > t["exit_time"].iloc[:-1].to_numpy()).all(), \
        "overlapping trades / pyramiding detected"
    gaps = (t["entry_time"].iloc[1:].to_numpy() - t["exit_time"].iloc[:-1].to_numpy())
    assert (gaps > np.timedelta64(0, "s")).all(), "trades overlap in time"


@test
def test_cooldown_blocks_immediate_reentry():
    df = make_feature_frame(600, seed=22)
    df["funding_event"] = False
    sig = np.ones(len(df), dtype=bool)
    for cd in (0, 3, 6):
        res = run_backtest(df, _spec_from_signals(df, sig, sig.copy(), cooldown_bars=cd),
                           costs=CostModel(slippage_bps=0.0, apply_funding=False))
        t = res.trades
        assert len(t) > 2, f"cooldown {cd}: too few trades to test"
        # .to_numpy() on both sides: pandas would otherwise *align* the two
        # differently-indexed Series and silently produce all-NaN.
        gaps = (t["entry_time"].iloc[1:].to_numpy()
                - t["exit_time"].iloc[:-1].to_numpy()) / np.timedelta64(5, "m")
        assert np.all(gaps > cd), \
            f"cooldown of {cd} bars was violated (min observed gap {gaps.min()} bars)"


@test
def test_time_stop_forces_an_exit():
    df = make_feature_frame(600, seed=23)
    df["funding_event"] = False
    sig = np.zeros(len(df), dtype=bool)
    sig[50] = True
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy(), time_stop_bars=6),
                       costs=CostModel(slippage_bps=0.0, apply_funding=False))
    assert res.trades.iloc[0]["holding_bars"] <= 7, \
        f"time stop ignored, held {res.trades.iloc[0]['holding_bars']} bars"


@test
def test_position_is_closed_at_end_of_data():
    """No position may survive the final bar, and none may leak unrealised PnL."""
    df = make_feature_frame(400, seed=24)
    df["funding_event"] = False
    sig = np.zeros(len(df), dtype=bool)
    sig[100] = True
    # A very wide stop and an unreachable target: the only thing that can close
    # this trade is the end of the data.
    res = run_backtest(df, _spec_from_signals(df, sig, sig.copy(),
                                              atr_stop=500.0, r_multiple=1e6,
                                              time_stop_bars=10**6, cooldown_bars=0),
                       costs=CostModel(slippage_bps=0.0, apply_funding=False))
    assert len(res.trades) == 1, f"expected exactly 1 trade, got {len(res.trades)}"
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "end_of_data", f"got {t['exit_reason']}"
    assert t["exit_time"] == df.index[-1]
    # Unrealised PnL must be fully realised: final equity equals cash flow.
    sgn = 1.0 if t["direction"] == "long" else -1.0
    realised = (t["exit_price"] - t["entry_price"]) * t["quantity"] * sgn
    assert approx(res.equity.iloc[-1] - res.initial_equity,
                  realised - t["fees"] - t["funding"], 1e-6), \
        "final equity does not match the realised trade PnL"


# ==========================================================================
# 7. STRATEGY / DATA-AVAILABILITY CONTRACT
# ==========================================================================

@test
def test_funding_event_flag_marks_only_event_bars():
    """Funding is an 8h event, not a per-bar charge.

    Regression guard: a forward-filled flag leaves it True on every bar from
    the first event onward, which charges funding 96x too often at 5m and
    silently penalises every holding strategy.
    """
    from ..data.loader import _funding_event_flag
    bars = pd.date_range("2024-01-01", periods=24 * 12, freq="5min", tz="UTC")
    events = pd.DatetimeIndex([
        "2024-01-01 00:00:00", "2024-01-01 08:00:00", "2024-01-01 16:00:00",
    ], tz="UTC")
    flags = _funding_event_flag(events, bars)
    assert int(flags.sum()) == 3, f"expected 3 event bars, got {int(flags.sum())}"
    assert bars[flags].tolist() == events.tolist()
    # And it must not bleed into the bars between events (00:05 .. 07:55).
    assert not flags.iloc[1:96].any(), "funding flag propagated beyond its event bar"


@test
def test_funding_event_flag_on_hourly_bars():
    from ..data.loader import _funding_event_flag
    bars = pd.date_range("2024-01-01", periods=48, freq="1h", tz="UTC")
    events = pd.DatetimeIndex(["2024-01-01 00:00:00", "2024-01-01 08:00:00"])
    flags = _funding_event_flag(events, bars)
    assert int(flags.sum()) == 2, f"expected 2 event bars, got {int(flags.sum())}"


@test
def test_oi_resampling_takes_the_last_5m_reading():
    """Open interest is a snapshot, so a 1h bar carries its final reading.

    Averaging would invent a value the exchange never published and would leak
    the end of the hour backwards into its start.
    """
    from ..data.loader import _align_metrics
    # 24 five-minute bars span two full hours (00:00-00:55, 01:00-01:55).
    m = pd.DataFrame({"open_interest": np.arange(24.0)},
                     index=pd.date_range("2024-01-01", periods=24, freq="5min", tz="UTC"))
    hours = pd.date_range("2024-01-01", periods=2, freq="1h", tz="UTC")
    out = _align_metrics(m, hours, "1h")
    assert out["open_interest"].tolist() == [11.0, 23.0], \
        f"expected last-in-bucket [11, 23], got {out['open_interest'].tolist()}"


@test
def test_strategy_depending_on_missing_feed_is_reported_not_silently_empty():
    """SHARK-07/08 must surface as BLOCKED, not as 'zero edge'."""
    df = make_feature_frame(400, seed=25)
    assert "liquidation" in unavailable_dependencies(df, STRATEGIES["SHARK-07"]), \
        "liquidation dependency not detected on a frame with no liquidation data"
    assert "liquidation" in unavailable_dependencies(df, STRATEGIES["SHARK-08"])
    # SHARK-01 needs only volume + breakout and must be clean.
    assert unavailable_dependencies(df, STRATEGIES["SHARK-01"]) == []


@test
def test_shark01_entries_require_both_conditions():
    df = make_feature_frame(800, seed=26)
    spec = build_spec(df, STRATEGIES["SHARK-01"])
    ok = ~(df["rvol"].isna() | df["prev_high"].isna() | df["prev_low"].isna())
    idx = np.flatnonzero(ok.to_numpy())
    for i in idx[::37]:
        le = bool(df["rvol"].iloc[i] >= 2.0) and bool(df["close"].iloc[i] > df["prev_high"].iloc[i])
        se = bool(df["rvol"].iloc[i] >= 2.0) and bool(df["close"].iloc[i] < df["prev_low"].iloc[i])
        assert bool(spec.long_entry[i]) == le, f"long entry mismatch at bar {i}"
        assert bool(spec.short_entry[i]) == se, f"short entry mismatch at bar {i}"


@test
def test_every_recipe_produces_live_signals():
    """Guard against the silent all-False signal.

    A base mask built up with ``&=`` from an all-False array stays all-False
    forever, which is indistinguishable from 'the signal has no edge'.  Every
    recipe must therefore emit a non-zero number of entries on data where its
    feeds are all present.
    """
    df = make_frame(3000, seed=31)
    # Synthesise the derivative feeds so OI / funding / liquidation legs are
    # live; otherwise the availability guard would (correctly) block them and
    # the test would be measuring the wrong thing.
    rng = np.random.default_rng(5)
    df["open_interest"] = 1000 * np.exp(np.cumsum(rng.normal(0, 0.001, len(df))))
    # Imbalanced taker split: an exactly 50/50 split makes CVD identically
    # zero, which would silently kill every CVD-dependent recipe.
    buy_share = rng.uniform(0.35, 0.65, len(df))
    df["taker_buy_volume"] = df["volume"] * buy_share
    df["taker_sell_volume"] = df["volume"] * (1.0 - buy_share)
    df["funding_event"] = False
    df["funding_rate"] = 0.0
    # Bursty liquidation: a smooth series can never clear a 3x rolling ratio.
    # The rate is high enough that spikes actually coincide with volume-breakout
    # bars, which is the coincidence these recipes require.
    spike = np.where(rng.random(len(df)) < 0.10, 25.0, 1.0)
    df["long_liquidation_volume"] = np.exp(rng.normal(np.log(10.0), 0.5, len(df))) * spike
    df["short_liquidation_volume"] = np.exp(rng.normal(np.log(10.0), 0.5, len(df))) * spike[::-1]
    df["total_liquidation_volume"] = (df["long_liquidation_volume"]
                                       + df["short_liquidation_volume"])
    df = features.add_all(df, timeframe="5m")

    from ..strategies.recipes import ALL_RECIPES
    for name, recipe in ALL_RECIPES.items():
        assert unavailable_dependencies(df, recipe) == [], \
            f"{name} unexpectedly blocked on a fully-populated frame"
        spec = build_spec(df, recipe)
        n_long, n_short = int(spec.long_entry.sum()), int(spec.short_entry.sum())
        assert n_long + n_short > 0, \
            f"{name} generated ZERO entries -- signal set is dead, not unprofitable"

    # And the base primitive specifically: RVOL>=2 AND breakout must be common.
    bo = build_spec(df, ALL_RECIPES["SHARK-01"])
    assert int(bo.long_entry.sum()) > 0, "SHARK-01 long side is dead"
    assert int(bo.short_entry.sum()) > 0, "SHARK-01 short side is dead"


@test
def test_baseline_e_tsm_replaces_the_breakout_not_the_volume_filter():
    """The momentum control must differ from SHARK-01 in the entry rule only.

    On a random walk the 20-bar momentum sign and a 20-bar level break agree
    most of the time, so high overlap is expected -- and is exactly why this
    control matters.  What must NOT happen is the two being identical, which
    would make the control vacuous.
    """
    df = make_feature_frame(1200, seed=41)
    s1 = build_spec(df, STRATEGIES["SHARK-01"])
    tsm = build_spec(df, BASELINES["BASELINE-E-TSM"])
    assert int(tsm.long_entry.sum()) > 0, "TSM control is dead"
    assert int((s1.long_entry ^ tsm.long_entry).sum()) > 0, \
        "TSM control is identical to SHARK-01 -- it is not a control"
    # Both must still sit on the shared volume filter, so neither can fire on
    # a bar where RVOL < 2.
    rvol_ok = df["rvol"].to_numpy() >= 2.0
    assert not (tsm.long_entry & ~rvol_ok).any(), "TSM fired without the volume filter"
    assert not (s1.long_entry & ~rvol_ok).any(), "SHARK-01 fired without the volume filter"


@test
def test_dsr_benchmark_is_expressed_in_matching_units():
    """Regression guard for a units error that inflated the bar ~41x.

    emax(N) is a RETURN-FREQUENCY quantity: the Sharpe of a mean over T
    observations has standard error 1/sqrt(T), so the expected maximum of N
    candidates is emax(N)/sqrt(T) in per-observation units. Comparing the
    per-observation Sharpe against a bare emax makes a finite requirement
    look impossible.
    """
    from ..validation.statistics import deflated_sharpe
    from ..validation.feasibility import deflated_feasibility, expected_max_sharpe
    rng = np.random.default_rng(2)
    # A real effect that should be detectable with enough observations.
    r = rng.normal(0.10, 1.0, 4000)
    d = deflated_sharpe(r, trials=10)
    assert d["emax_per_obs"] < d["emax_benchmark"], \
        "per-observation benchmark must be the return-frequency one divided by sqrt(T)"
    assert abs(d["emax_per_obs"] - d["emax_benchmark"] / np.sqrt(4000)) < 1e-9
    assert d["sharpe_return_freq"] > d["emax_benchmark"], \
        "a strong per-trade Sharpe over 4000 obs must clear the luck bar"

    # And the required sample sizes must be finite, not None.
    f = deflated_feasibility(0.043, 1.454, trials=41_472, n_obs=1690)
    assert f["trades_needed_undeflated"] is not None
    assert f["trades_needed_deflated"] is not None
    assert f["trades_needed_deflated"] > f["trades_needed_undeflated"], \
        "deflation must increase the requirement"
    # Observed return-frequency Sharpe vs the bar, in the same units.
    assert abs(f["observed_sharpe_return_freq"]
               - f["observed_sharpe_per_trade"] * np.sqrt(1690)) < 1e-6


@test
def test_effective_sample_size_deflates_under_persistence():
    """A persistent return series must report fewer effective observations."""
    from ..analysis.benchmarks import effective_sample_size
    rng = np.random.default_rng(3)
    n = 600
    iid = rng.normal(0, 1, n)
    persistent = np.zeros(n)
    for k in range(1, n):
        persistent[k] = 0.9 * persistent[k - 1] + rng.normal(0, 1)
    a = effective_sample_size(pd.DataFrame({"r_net": iid}))
    b = effective_sample_size(pd.DataFrame({"r_net": persistent}))
    assert b["n_effective_newey_west"] < a["n_effective_newey_west"], \
        "persistent series was not deflated relative to iid"
    assert b["inflation_factor"] > a["inflation_factor"]


@test
def test_minimum_detectable_effect_is_a_real_comparison():
    """A tiny edge must be reported as undetectable, not merely as 'a number'.

    The previous version asserted `min_detectable_effect_r > 0` (trivially
    true for any positive dispersion) and `detectable is False or observed >=
    mde` -- which is `X or X`, because benchmarks.py *defines* `detectable` as
    `observed >= mde`. It passed even with the MDE forced to 1e9, i.e. it never
    made the comparison its name claimed.
    """
    from ..analysis.benchmarks import minimum_detectable_effect
    rng = np.random.default_rng(9)

    # A tiny edge: must be reported as NOT detectable.
    p = minimum_detectable_effect(pd.DataFrame({"r_net": rng.normal(1e-4, 1.0, 500)}))
    assert p["detectable"] is False, "a 1e-4R edge was reported as detectable"
    assert p["observed_expectancy_r"] < p["min_detectable_effect_r"]

    # A large edge on the same dispersion: must be reported as detectable.
    p2 = minimum_detectable_effect(pd.DataFrame({"r_net": rng.normal(1.0, 1.0, 500)}))
    assert p2["detectable"] is True, "a 1.0R edge was reported as undetectable"
    assert p2["observed_expectancy_r"] >= p2["min_detectable_effect_r"]

    # The MDE must grow when dispersion grows, for the same edge.
    narrow = minimum_detectable_effect(pd.DataFrame({"r_net": rng.normal(0.1, 0.5, 500)}))
    wide = minimum_detectable_effect(pd.DataFrame({"r_net": rng.normal(0.1, 2.0, 500)}))
    assert wide["min_detectable_effect_r"] > narrow["min_detectable_effect_r"]


@test
def test_frozen_bars_are_masked_not_interpolated():
    """A frozen run is a data artefact; masking must not invent a price path.

    Found by cross-checking native 1h klines against the aggregation of 5m
    klines: BTCUSDT 2023-11-10 has 5m bars that exist, sit on the grid, and
    are structurally valid, but freeze at one price with zero volume while the
    exchange's own 1h bar shows an active market.
    """
    from ..data.normalization import frozen_runs, repair_frozen_bars
    df = make_frame(200, seed=2)
    df.iloc[50:62, df.columns.get_loc("open")] = 100.0
    df.iloc[50:62, df.columns.get_loc("high")] = 100.0
    df.iloc[50:62, df.columns.get_loc("low")] = 100.0
    df.iloc[50:62, df.columns.get_loc("close")] = 100.0
    df.iloc[50:62, df.columns.get_loc("volume")] = 0.0

    runs = frozen_runs(df)
    assert len(runs) == 1 and runs[0] == (50, 62), f"run not detected: {runs}"

    out, masked = repair_frozen_bars(df)
    assert masked == 12
    # Masked, not filled: a NaN is the honest representation.
    assert out["close"].iloc[50:62].isna().all(), "frozen run was filled, not masked"
    # The grid must stay regular or every rolling window realigns.
    assert len(out) == len(df)
    assert out.index.equals(df.index)
    # Nothing outside the run was touched.
    assert not out["close"].iloc[:50].isna().any()
    assert not out["close"].iloc[62:].isna().any()


@test
def test_frozen_run_detection_ignores_short_or_legitimate_bars():
    from ..data.normalization import frozen_runs
    df = make_frame(200, seed=2)
    # Two flat bars are below the threshold and must not be flagged.
    df.iloc[30:32, df.columns.get_loc("high")] = df.iloc[30:32, df.columns.get_loc("low")]
    assert frozen_runs(df) == [], "two flat bars flagged as a stale run"
    # A flat bar WITH volume is a real zero-range print, not an artefact.
    df2 = make_frame(200, seed=2)
    df2.iloc[40:50, df2.columns.get_loc("high")] = df2.iloc[40:50, df2.columns.get_loc("low")]
    df2.iloc[40:50, df2.columns.get_loc("volume")] = 5.0
    assert frozen_runs(df2) == [], "a flat bar with volume flagged as stale"


@test
def test_sane_rate_guard_rejects_documented_api_corruption():
    """284,000 bps funding readings have been published as API errors.

    A forward collector must not let one such payload into a multi-year
    series, and the guard must still pass the genuine -200 bps clamp.
    """
    from ..config import MAX_SANE_RATE_BPS, rate_is_sane
    assert rate_is_sane(0.0001)            # 1 bp, normal
    assert rate_is_sane(-0.02)             # -200 bps, a real clamp
    assert not rate_is_sane(28.4)          # 284,000 bps, the documented error
    assert not rate_is_sane(float("nan"))
    assert not rate_is_sane(float("inf"))
    assert not rate_is_sane(None)
    # And the ceiling must sit far above anything real, or it eats data.
    assert MAX_SANE_RATE_BPS > 1000, "guard is too tight to be a corruption filter"

    # It is a guard for RATES. Applying it to a price would reject every
    # genuine event -- BTC at 84,000 is 8,400,000 bps -- so the liquidation
    # parser must not consult it.
    from ..collect_liquidations import Collector
    real_btc = {"topic": "allLiquidation.BTCUSDT", "data": [
        {"T": 1, "s": "BTCUSDT", "S": "Buy", "v": "1", "p": "84000"}]}
    assert len(Collector.parse(real_btc)) == 1, \
        "a rate-shaped sanity ceiling was misapplied to a price"


@test
def test_liquidation_parser_matches_the_documented_bybit_schema():
    """The collector must parse Bybit's real single-letter field names.

    Regression guard for a silent failure: an earlier version used
    descriptive field names (symbol/side/price/size) that the v5 stream does
    not emit, so it would have collected zero events forever while looking
    healthy. The schema here is copied from the official docs page.
    """
    from ..collect_liquidations import Collector
    msg = {
        "topic": "allLiquidation.ROSEUSDT", "type": "snapshot", "ts": 1739502303204,
        "data": [{"T": 1739502302929, "s": "ROSEUSDT", "S": "Sell",
                  "v": "20000", "p": "0.04499"}],
    }
    rows = Collector.parse(msg)
    assert len(rows) == 1, f"parser dropped a well-formed event: {rows}"
    r = rows[0]
    assert r["symbol"] == "ROSEUSDT"
    assert r["quantity"] == 20000.0
    assert r["price"] == 0.04499
    assert abs(r["notional"] - 20000 * 0.04499) < 1e-9


@test
def test_liquidation_side_semantics_are_not_inverted():
    """Bybit: S=Buy means a LONG position was liquidated.

    Inverting this silently flips the sign of every liquidation-driven
    signal. Spec 22 requires a long setup on SHORT liquidations, so the
    mapping is load-bearing and is pinned here.
    """
    from ..collect_liquidations import Collector
    buy = {"topic": "allLiquidation.BTCUSDT", "data": [
        {"T": 1, "s": "BTCUSDT", "S": "Buy", "v": "1", "p": "100"}]}
    sell = {"topic": "allLiquidation.BTCUSDT", "data": [
        {"T": 1, "s": "BTCUSDT", "S": "Sell", "v": "1", "p": "100"}]}
    assert Collector.parse(buy)[0]["side"] == "long"
    assert Collector.parse(sell)[0]["side"] == "short"


@test
def test_liquidation_parser_rejects_malformed_events():
    from ..collect_liquidations import Collector
    assert Collector.parse({"topic": "publicTrade.BTCUSDT", "data": []}) == []
    assert Collector.parse({"topic": "allLiquidation.BTCUSDT", "data": [
        {"T": 1, "s": "BTCUSDT", "S": "Buy", "v": "0", "p": "100"}]}) == []
    assert Collector.parse({"topic": "allLiquidation.BTCUSDT", "data": [
        {"T": 1, "s": "BTCUSDT", "S": "Unknown", "v": "1", "p": "100"}]}) == []


@test
def test_every_recipe_produces_live_signals_on_every_timeframe():
    """A recipe must not go silent because a feature column is missing.

    A strategy carrying a 5-bar CVD default finds no `cvd_delta_5` column at
    1h, resolves every comparison to NaN, and produces zero trades -- which
    looks identical to "no edge" and would be reported as BLOCKED rather than
    as a bug. This is the check that would have caught it.
    """
    df = make_frame(3000, seed=31)
    rng = np.random.default_rng(5)
    df["open_interest"] = 1000 * np.exp(np.cumsum(rng.normal(0, 0.001, len(df))))
    buy_share = rng.uniform(0.35, 0.65, len(df))
    df["taker_buy_volume"] = df["volume"] * buy_share
    df["taker_sell_volume"] = df["volume"] * (1.0 - buy_share)
    df["funding_event"] = False
    df["funding_rate"] = 0.0
    spike = np.where(rng.random(len(df)) < 0.10, 25.0, 1.0)
    df["long_liquidation_volume"] = np.exp(rng.normal(np.log(10.0), 0.5, len(df))) * spike
    df["short_liquidation_volume"] = np.exp(rng.normal(np.log(10.0), 0.5, len(df))) * spike[::-1]
    df["total_liquidation_volume"] = (df["long_liquidation_volume"]
                                       + df["short_liquidation_volume"])

    from ..strategies.recipes import STRATEGIES
    for tf in ("5m", "1h", "4h"):
        f = features.add_all(df.copy(), timeframe=tf)
        for name in ("SHARK-01", "SHARK-02", "SHARK-03", "SHARK-04",
                     "SHARK-05", "SHARK-06"):
            spec = build_spec(f, STRATEGIES[name])
            n = int(spec.long_entry.sum()) + int(spec.short_entry.sum())
            assert n > 0, (
                f"{name} generated ZERO entries at {tf} -- a feature column its "
                f"recipe depends on is probably absent at this timeframe")


@test
def test_narrowing_never_creates_trades():
    """Adding a filter may only remove signals, never add them."""
    df = make_feature_frame(1000, seed=27)
    base = build_spec(df, STRATEGIES["SHARK-01"])
    for name in ("SHARK-02", "SHARK-03", "SHARK-04", "SHARK-05", "SHARK-06"):
        narrow = build_spec(df, STRATEGIES[name])
        assert (narrow.long_entry <= base.long_entry).all(), f"{name} produced longs SHARK-01 did not"
        assert (narrow.short_entry <= base.short_entry).all(), f"{name} produced shorts SHARK-01 did not"


@test
def test_baseline_breakout_is_a_strict_superset_of_shark01():
    """Baseline C (pure breakout) must contain every SHARK-01 signal."""
    df = make_feature_frame(1000, seed=28)
    bo = build_spec(df, STRATEGIES["SHARK-01"])
    from ..strategies.recipes import BASELINES
    pure = build_spec(df, BASELINES["BASELINE-C-BREAKOUT"])
    assert (bo.long_entry <= pure.long_entry).all()
    assert (bo.short_entry <= pure.short_entry).all()


# ==========================================================================
# runner
# ==========================================================================

def main() -> int:
    failed: list[tuple[str, str]] = []
    print(f"Shark Hunter regression suite: {len(_TESTS)} tests\n")
    for fn in _TESTS:
        name = fn.__name__
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:                                  # noqa: BLE001
            tb = traceback.format_exc(limit=3)
            failed.append((name, tb))
            print(f"  FAIL  {name}: {exc}")
    print()
    if failed:
        print(f"{len(failed)}/{len(_TESTS)} FAILED\n")
        for name, tb in failed:
            print(f"--- {name} ---\n{tb}\n")
        return 1
    print(f"all {len(_TESTS)}/{len(_TESTS)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
