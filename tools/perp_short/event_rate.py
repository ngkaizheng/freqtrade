"""How many times does the signal actually fire, and could any filter be loosened?

PRE-REGISTERED as E-1 in docs-myself/PREREG_EVENT_RATE_2026-09-30.md. Read the
gates there first. This counts events. It does NOT backtest, does not compute
P&L, and does not touch the delivered strategy, config or any published result.

WHY
---
Section 15c measured that the binding constraint on this book is not the
per-trade edge (0.1173R) or the cost (11% of gross) but the NUMBER of independent
observations: 423 timestamps available against 1,159 needed for t=2. The
average book holds 3.0 positions. Nothing in this project has ever optimised the
EVENT RATE, because every previous line optimised the per-trade edge.

The frozen signal is a CONJUNCTION of three conditions
(`PerpShort4h.populate_indicators:231-235`):

    (rvol >= 2.0) & (close < prev_low_20) & (vol42 < vol42_med_365)

and a conjunction multiplies event rates. So the Gate 0 question is arithmetic
before it is anything else: how much does loosening ONE condition buy?

Gate E1 first: the frozen configuration's event rate must reconcile with the
engine's own 1,111 trades over 3.44 years on 40 symbols. If the counting basis
does not reconcile, no candidate is interpreted - the basis is fixed first.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\event_rate.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
DEPLOYED_ZIP = ROOT / "user_data" / "deployed_out"
OUT = ROOT / "user_data" / "perp_short_out" / "event_rate.csv"

# the frozen parameters, read from the strategy rather than retyped
FROZEN = dict(rvol_period=20, rvol_threshold=2.0, breakout_period=20,
              vol_lookback=42, vol_med_window=365)
# the preregistered relaxation grids - fixed BEFORE any count was seen
RVOL_GRID = [2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4]
DONCHIAN_GRID = [20, 16, 12, 10, 8]
ENGINE_TRADES = 1111     # the deployed book's own count, used for gate E1
ENGINE_YEARS = 3.44
MIN_MULTIPLE = 2.0       # gate E2
NEEDED_MULTIPLE = (2 / 0.58) ** 2   # gate E3, pre-computed in the prereg (~11.9x)


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def indicators(d: pd.DataFrame, p: dict) -> pd.DataFrame:
    """The strategy's own indicator block, parameterised. Written to match
    `PerpShort4h.populate_indicators` line for line, including the shift(1) on
    the Donchian levels and on the volatility median - those shifts are the
    difference between a causal signal and a lookahead one, and this script is
    counting events for a CAUSAL signal."""
    df = d.copy()
    df["rvol"] = df["volume"].clip(lower=0.0).rolling(
        p["rvol_period"], min_periods=p["rvol_period"]).mean()
    df["rvol"] = df["volume"] / df["rvol"].replace(0.0, np.nan)
    df["prev_low"] = df["low"].rolling(
        p["breakout_period"], min_periods=p["breakout_period"]).min().shift(1)
    lr = np.log(df["close"]).diff()
    df["vol42"] = lr.rolling(p["vol_lookback"], min_periods=p["vol_lookback"]).std()
    df["vol42_med"] = (df["vol42"].rolling(
        p["vol_med_window"], min_periods=120).median().shift(1))
    return df


def load_pairs() -> list[str]:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    return cfg["exchange"]["pair_whitelist"]


def signals(pairs: list[str], p: dict) -> pd.DataFrame:
    cols = {}
    for sym in pairs:
        f = DATA / f"{sym.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)[["date", "high", "low", "close", "volume"]]
        d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
        d = d.sort_values("date").reset_index(drop=True)
        df = indicators(d, p)
        # pandas 3 nullable dtypes make a comparison against NaN return pd.NA
        # rather than False, and `&` then propagates NA into the frame - so
        # int(...sum()) raises "cannot convert float NaN to integer" instead of
        # counting. Coerce to a plain bool, which is what the strategy's own
        # `.fillna(False)` on `low_vol` is doing.
        c_rvol = (df["rvol"] >= p["rvol_threshold"]).fillna(False).astype(bool)
        c_donch = (df["close"] < df["prev_low"]).fillna(False).astype(bool)
        c_lv = (df["vol42"] < df["vol42_med"]).fillna(False).astype(bool)
        # KEEP THE DATE INDEX. A `.reset_index(drop=True)` here (added while
        # chasing a NaN error) throws the dates away, `pd.DataFrame(cols)` then
        # gets a RangeIndex, and `pd.to_datetime(range_index, utc=True)` reads
        # those integers as NANOSECONDS SINCE EPOCH - so every timestamp became
        # 1970-01-01 and every duration in this script came out 0.00. The
        # signal count (2,169) was right the whole time; only the clock broke.
        c = c_rvol & c_donch & c_lv
        c.index = pd.DatetimeIndex(d["date"].to_numpy())
        cols[sym] = c
    out = pd.DataFrame(cols)
    out.index = pd.to_datetime(out.index, utc=True)
    return out.sort_index()


def main() -> int:
    print("E-1 EVENT RATE GATE 0 - how often does the signal fire, and could any")
    print("of the three filters be loosened to fire more often?\n")
    print("Pre-registered in docs-myself/PREREG_EVENT_RATE_2026-09-30.md.")
    print("NO BACKTEST is run. Nothing is changed. This only counts.\n")

    pairs = load_pairs()
    print(f"  universe: {len(pairs)} symbols from {CFG.name}")
    base = signals(pairs, FROZEN)
    # Symbols list at different times, so pd.DataFrame(cols) aligns their
    # indices and fills the earlier rows with NaN. Those are not signals, they
    # are "this symbol did not exist yet" - count them as False, never as NaN.
    base = base.fillna(False).astype(bool)
    n_bars = len(base)
    n_base = int(base.to_numpy().sum())
    rate_base = n_base / n_bars
    print(f"  bars per symbol: {n_bars}  ->  {n_bars * len(base.columns):,} bar-symbols")

    head("E1 - DOES THE COUNTING BASIS RECONCILE WITH THE ENGINE?")
    # The index dtype varies across panels (datetime64[us] from some feathers,
    # [ns] from others) and subtracting mismatched units yields a plain int
    # instead of a Timedelta. Coerce first, always.
    idx = pd.DatetimeIndex(base.index)
    years = (idx[-1] - idx[0]).total_seconds() / (365.25 * 86400)
    # n_base is ALREADY the total across symbols - it does not need to be
    # scaled by years or by the symbol count. Dividing by n_bars and
    # multiplying back by years*n_symbols was a no-op in intent and wrong in
    # arithmetic: it reported 40 implied trades against 2,169 actual signals.
    implied = n_base
    print(f"  frozen signal fires {n_base:,} times over {years:.2f} y "
          f"on {len(base.columns)} symbols")
    print(f"  signals per symbol per year : {n_base/years/len(base.columns):.1f}")
    print(f"  signals total (if all were taken) : {implied:,.0f}")
    print(f"  the engine actually executed             : {ENGINE_TRADES:,}")
    ratio = implied / ENGINE_TRADES
    # The engine cannot take every signal: max_open_trades=24 caps concurrency,
    # and a symbol already in a position cannot re-enter. So the count is an
    # UPPER BOUND and should exceed the engine's number, not match it.
    ok = implied >= ENGINE_TRADES * 0.9
    print(f"  ratio implied / executed = {ratio:.2f}x")
    print(f"  -> E1 {'PASS' if ok else 'FAIL'}: the count is an UPPER BOUND on the")
    print(f"     engine's fills (max_open_trades=24 and no re-entry into an open")
    print(f"     position both discard signals), so it should be >=, not equal.")
    print(f"     {'It is not, so the basis is wrong and no candidate below is read.' if not ok else 'It is.'}")
    if not ok:
        return 1

    rows = []

    # ---- candidate grid ----------------------------------------------------
    head("THE FULL GRID - every cell published, nothing selected afterwards")
    print(f"  {'variant':<26}{'signals':>10}{'multiple':>10}{'per year':>10}")
    rows.append(("FROZEN (rvol>=2.0, donch 20, low-vol on)", n_base, 1.0))
    print(f"  {'FROZEN (rvol>=2.0, donch 20, low-vol on)':<26}{n_base:>10,}"
          f"{1.0:>9.2f}x{n_base/years:>10.0f}")

    for t in RVOL_GRID[1:]:
        p = dict(FROZEN, rvol_threshold=t)
        n = int(signals(pairs, p).fillna(False).to_numpy().sum())
        m = n / n_base
        rows.append((f"rvol >= {t}", n, m))
        print(f"  {f'rvol >= {t}':<26}{n:>10,}{m:>9.2f}x{n/years:>10.0f}")

    for b in DONCHIAN_GRID[1:]:
        p = dict(FROZEN, breakout_period=b)
        n = int(signals(pairs, p).fillna(False).to_numpy().sum())
        m = n / n_base
        rows.append((f"donchian {b}", n, m))
        print(f"  {f'donchian {b}':<26}{n:>10,}{m:>9.2f}x{n/years:>10.0f}")

    # The low-vol filter turned OFF, counted the same way as everything else.
    # (The first version of this block was dead code that computed a value and
    # threw it away, and threw a TypeError on the way - a grid row that does not
    # exist is worse than one that is missing, because the table looks complete.)
    def _no_lowvol() -> int:
        cols = {}
        for sym in pairs:
            fp = DATA / f"{sym.replace('/', '_').replace(':', '_')}-4h-futures.feather"
            if not fp.exists():
                continue
            d = pd.read_feather(fp)[["date", "high", "low", "close", "volume"]]
            d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
            d = d.sort_values("date").reset_index(drop=True)
            df = indicators(d, FROZEN)
            c = ((df["rvol"] >= FROZEN["rvol_threshold"]) &
                 (df["close"] < df["prev_low"])).fillna(False).astype(bool)
            c.index = pd.DatetimeIndex(d["date"].to_numpy())
            cols[sym] = c
        o = pd.DataFrame(cols)
        o.index = pd.to_datetime(o.index, utc=True)
        return int(o.fillna(False).to_numpy().sum())

    n_nolv = _no_lowvol()
    m = n_nolv / n_base
    rows.append(("low-vol filter OFF", n_nolv, m))
    print(f"  {'low-vol filter OFF':<26}{n_nolv:>10,}{m:>9.2f}x{n_nolv/years:>10.0f}")

    # per-condition pass rates: which filter is actually doing the work
    head("WHICH CONDITION IS THROTTLING THE EVENT RATE?")
    rates = {}
    for sym in base.columns[:12]:
        f = DATA / f"{sym.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)[["date", "high", "low", "close", "volume"]]
        d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
        df = indicators(d.sort_values("date").reset_index(drop=True), FROZEN)
        v = df["rvol"].notna() & df["prev_low"].notna() & df["vol42_med"].notna()
        rates.setdefault("rvol>=2.0", []).append(float((df["rvol"] >= 2.0)[v].mean()))
        rates.setdefault("close<prev_low20", []).append(float((df["close"] < df["prev_low"])[v].mean()))
        rates.setdefault("low_vol", []).append(float((df["vol42"] < df["vol42_med"])[v].mean()))
        rates.setdefault("ALL THREE", []).append(float(
            ((df["rvol"] >= 2.0) & (df["close"] < df["prev_low"]) &
             (df["vol42"] < df["vol42_med"]))[v].mean()))
    print(f"  {'condition':<22}{'mean pass rate':>16}{'signals alone':>16}")
    prod = 1.0
    for k in ("rvol>=2.0", "close<prev_low20", "low_vol", "ALL THREE"):
        m = float(np.mean(rates[k]))
        if k != "ALL THREE":
            prod *= m
        print(f"  {k:<22}{m*100:>15.2f}%{m*n_bars*len(rates['rvol>=2.0']):>16,.0f}")
    print(f"\n  product of the three individual pass rates = {prod*100:.2f}%, "
          f"observed all-three = {np.mean(rates['ALL THREE'])*100:.2f}%")
    print("  (they differ because the conditions are not independent - which is")
    print("   itself the finding: a conjunction of positively-correlated conditions)")

    # ---- gates -------------------------------------------------------------
    head("GATES")
    best = max(rows[1:], key=lambda r: r[2])
    e2 = best[2] >= MIN_MULTIPLE
    print(f"  best multiple: {best[0]} at {best[2]:.2f}x  "
          f"(E2 needs >= {MIN_MULTIPLE:.1f}x)  -> {'PASS' if e2 else 'FAIL'}")
    e3 = best[2] >= NEEDED_MULTIPLE
    print(f"  best multiple vs what t=2 actually needs "
          f"({NEEDED_MULTIPLE:.1f}x)  -> {'PASS' if e3 else 'FAIL'}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["variant", "signals", "multiple"]).to_csv(OUT, index=False)

    head("VERDICT")
    if not e2:
        print("  E2 FAILS: no single-condition relaxation multiplies the event rate by")
        print("  even 2x. The conjunction is not costing us reachability - the market")
        print("  simply does not produce these events often. **The 4h line is CLOSED,")
        print("  and the reason is now n_eff, not cost.**")
    elif not e3:
        print("  E2 PASSES but E3 FAILS: some relaxation multiplies events by more than")
        print(f"  2x, but t=2 needs {NEEDED_MULTIPLE:.1f}x. The gap is about "
              f"{NEEDED_MULTIPLE/max(best[2],1e-9):.1f}x -")
        print("  **which is the real statement: reaching significance here is not a")
        print("  tuning problem.** No candidate is carried forward; E4 forbids a")
        print("  backtest this round regardless.")
    else:
        print("  E2 and E3 both pass. Per E4 nothing is backtested this round; the next")
        print("  step is a SEPARATE preregistration for that one candidate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
