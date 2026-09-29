"""Are the signals graded, or are they all the same? (the WEIGHT axis, not the COUNT axis)

PRE-REGISTERED as Q-1 in docs-myself/PREREG_SIGNAL_STRENGTH_2026-09-30.md. Read
the gates there first.

WHY THIS IS A DIFFERENT AXIS FROM EVERYTHING BEFORE
---------------------------------------------------
E-1 measured the COUNT axis: loosening any of the three filters buys at most
1.88x more events against 11.9x needed, because the three conditions fire on the
same bars. That closes "which bars should we trade".

This tests the WEIGHT axis, which nobody has touched: **among the SAME 2,169
signals, is a stronger one followed by a bigger move?** Threshold tuning changes
WHICH bars trade; strength weighting changes HOW MUCH. Weighting is not
constrained by the event rate at all - it needs no additional trades.

It matters because it is the only conventional route from signal QUALITY to
statistical POWER: weighting by a predictor that predicts the outcome moves the
weighted mean up faster than the weighted variance, which is what t measures.

This is a GATE 0. It reads forward returns off the price panel and computes
nothing else. No backtest, no positions, no stops, no P&L, and nothing in the
delivered system is touched.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\signal_strength.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from event_rate import FROZEN, indicators  # noqa: E402
from r_stats import tstat  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
OUT = ROOT / "user_data" / "perp_short_out" / "signal_strength.csv"

HOLD = 42          # 42 4h bars = 7 days, the strategy's own time_stop_bars
RVOL_BINS = [2.0, 2.5, 3.0, 4.0, np.inf]     # preregistered boundaries
N_DEPTH_QUARTILES = 4
EXPECTED_SIGNALS = 2169                        # from E-1, used by gate Q1
TOL = 0.01


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def build(pairs: list[str]) -> pd.DataFrame:
    """One row per SIGNAL: rvol, breakout depth, and the forward HOLD-bar return."""
    rows = []
    for sym in pairs:
        f = DATA / f"{sym.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)[["date", "high", "low", "close", "volume"]]
        d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
        d = d.sort_values("date").reset_index(drop=True)
        df = indicators(d, FROZEN)
        c_rvol = (df["rvol"] >= FROZEN["rvol_threshold"]).fillna(False).astype(bool)
        c_donch = (df["close"] < df["prev_low"]).fillna(False).astype(bool)
        c_lv = (df["vol42"] < df["vol42_med"]).fillna(False).astype(bool)
        sig = (c_rvol & c_donch & c_lv).to_numpy()
        if not sig.any():
            continue
        # forward return over the strategy's own holding horizon
        fwd = df["close"].shift(-HOLD) / df["close"] - 1.0
        depth = df["prev_low"] / df["close"] - 1.0          # >0, how far below
        for i in np.flatnonzero(sig):
            fr = fwd.iloc[i]
            dp = depth.iloc[i]
            if not (np.isfinite(fr) and np.isfinite(dp)):
                continue
            rows.append({"pair": sym, "i": int(i),
                         "date": df["date"].iloc[i],
                         "rvol": float(df["rvol"].iloc[i]),
                         "depth": float(dp), "fwd": float(fr)})
    return pd.DataFrame(rows)


def bucketize(s: pd.Series, edges: list[float], labels: list[str]) -> pd.Series:
    idx = np.digitize(s.to_numpy(), edges[1:-1], right=False)
    return pd.Series([labels[i] if i < len(labels) else labels[-1] for i in idx],
                     index=s.index)


def monotone_decreasing(means: list[float]) -> bool:
    """Strictly decreasing left to right. Equal means do NOT count: a tie is
    evidence the axis is noise, and 'not worse' is not 'graded'."""
    return all(means[i] > means[i + 1] for i in range(len(means) - 1))


def main() -> int:
    print("Q-1 SIGNAL STRENGTH GATE 0 - is the signal GRADED, or is it all-or-nothing?\n")
    print("Pre-registered in docs-myself/PREREG_SIGNAL_STRENGTH_2026-09-30.md.")
    print(f"Forward return is {HOLD} x 4h = {HOLD*4/24:.0f} days, the strategy's own")
    print("time_stop_bars. A SHORT is profitable when the forward return is NEGATIVE.\n")
    print("No backtest. No positions. Nothing is changed.\n")

    pairs = json.loads(CFG.read_text(encoding="utf-8"))["exchange"]["pair_whitelist"]
    print(f"  universe: {len(pairs)} symbols")
    sig = build(pairs)
    n = len(sig)

    head("Q1 - DOES THE SAMPLE RECONCILE WITH E-1?")
    print(f"  signals: {n:,}   E-1 reported: {EXPECTED_SIGNALS:,}   "
          f"difference: {abs(n-EXPECTED_SIGNALS)/EXPECTED_SIGNALS*100:.2f}%")
    q1 = abs(n - EXPECTED_SIGNALS) / EXPECTED_SIGNALS <= TOL
    print(f"  -> Q1 {'PASS' if q1 else 'FAIL'}")
    if not q1:
        print("     (E-1 dropped the last HOLD bars' signals because the forward")
        print("      return was undefined there; a small shortfall is expected and")
        print("      is bounded, a large one is not.)")
        if not q1:
            print("     A difference this large means the basis changed. No number")
            print("     below is interpreted.")
            return 1

    head("Q2 - IS THE SIGN DIRECTION EVEN RIGHT?")
    t_all, m_all, _, _ = tstat(sig["fwd"].to_numpy())
    print(f"  all {n:,} signals: mean forward return {m_all*100:+.3f}%   t = {t_all:+.2f}")
    print(f"  a short profits when this is NEGATIVE -> Q2 "
          f"{'PASS' if m_all < 0 else 'FAIL'}")
    if m_all >= 0:
        print("  the direction is wrong, so nothing below can be right.")
        return 1
    print(f"  the panel's unconditional mean over the same window: see below, for scale")

    head("Q3/Q4 - IS THE SIGNAL GRADED IN rvol? (the decisive gate)")
    labels = [f"[{RVOL_BINS[i]:.1f},{RVOL_BINS[i+1]:.1f})"
              for i in range(len(RVOL_BINS) - 1)]
    sig["bin"] = bucketize(sig["rvol"], RVOL_BINS, labels)
    print(f"  {'rvol bin':<16}{'n':>8}{'mean fwd %':>13}{'median %':>12}{'t':>8}{'win%':>8}")
    means, counts = [], []
    for b in labels:
        sub = sig[sig["bin"] == b]
        if len(sub) < 30:
            print(f"  {b:<16}{len(sub):>8}   too few to use")
            continue
        t, m, _, _ = tstat(sub["fwd"].to_numpy())
        means.append(m)
        counts.append(len(sub))
        print(f"  {b:<16}{len(sub):>8,}{m*100:>13.3f}{sub['fwd'].median()*100:>12.3f}"
              f"{t:>8.2f}{(sub['fwd'] < 0).mean()*100:>7.1f}%")
    q3 = len(means) >= 3 and monotone_decreasing(means)
    print(f"\n  means (left to right): {[f'{m*100:+.3f}%' for m in means]}")
    print(f"  -> Q3 strictly decreasing: {'PASS' if q3 else 'FAIL'}")
    if len(means) >= 2 and q3:
        top, bot = means[0], means[-1]
        # Q4: the DIFFERENCE OF MEANS, standardised. The first version subtracted
        # the two raw sample ARRAYS (different lengths) and raised
        # "operands could not be broadcast" - a statistic written as a-b that
        # silently wanted a-b/n. The prereg says "the difference between the
        # strongest and weakest bucket's mean", so that is what is computed.
        a = sig.loc[sig["bin"] == labels[0], "fwd"].to_numpy()
        b = sig.loc[sig["bin"] == labels[-1], "fwd"].to_numpy()
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        diff = (a.mean() - b.mean()) / se
        q4 = diff >= 2.0      # weakest bucket must be MORE negative -> a.mean - b.mean > 0
        print(f"  strongest bucket mean {a.mean()*100:+.3f}%  vs weakest "
              f"{b.mean()*100:+.3f}%")
        print(f"  difference of means: {diff:+.2f} standard errors "
              f"-> Q4 {'PASS' if q4 else 'FAIL'} (needs >= +2)")
        print(f"  in basis points, the spread is "
              f"{abs(a.mean()-b.mean())*1e4:.0f} bps over 7 days.")
        print(f"  measured round trip is 12.0 bps (calm) to 34.9 bps (COVID) "
              f"-> the spread clears it by")
        print(f"  {abs(a.mean()-b.mean())*1e4/34.9:.0f}x to "
              f"{abs(a.mean()-b.mean())*1e4/12.0:.0f}x.")
    else:
        q4 = False
        print("  -> Q4 not evaluable without a monotone Q3.")

    head("Q5 - BREAKOUT DEPTH, AS AN INDEPENDENT DIMENSION (reported, not selected on)")
    try:
        sig["depth_q"] = pd.qcut(sig["depth"], N_DEPTH_QUARTILES,
                                 labels=[f"Q{i+1}" for i in range(N_DEPTH_QUARTILES)])
    except ValueError:
        sig["depth_q"] = pd.Series(["Q1"] * len(sig))
    print("  (Q1 = shallowest breach, Q4 = deepest)")
    print(f"  {'depth quartile':<18}{'n':>8}{'mean fwd %':>13}{'t':>8}")
    dmeans = []
    for q in [f"Q{i}" for i in range(1, N_DEPTH_QUARTILES + 1)]:
        sub = sig[sig["depth_q"] == q]
        if len(sub) < 30:
            continue
        t, m, _, _ = tstat(sub["fwd"].to_numpy())
        dmeans.append(m)
        print(f"  {q:<18}{len(sub):>8,}{m*100:>13.3f}{t:>8.2f}")
    print(f"  means: {[f'{m*100:+.3f}%' for m in dmeans]}")
    print("  reported for completeness; the prereg does not allow selecting on it.")

    sig.to_csv(OUT, index=False)
    print(f"\n  per-signal table written: {OUT.relative_to(ROOT)}  ({len(sig):,} rows)")

    # ---------------------------------------------------------------------
    # OUT-OF-SAMPLE CHECK. Added AFTER seeing the result, and declared as a
    # falsification test rather than a gate: nothing is selected on it, and a
    # failure is reported as a failure. The split is the one this project
    # already froze for its walk-forward work (dev 2023-01->2024-12,
    # OOS 2025-01->2026-08), not a boundary chosen now.
    # ---------------------------------------------------------------------
    head("OUT-OF-SAMPLE: does the gradient replicate in a window never used to see it?")
    sig["date"] = pd.to_datetime(sig["date"], utc=True)
    split = pd.Timestamp("2025-01-01", tz="UTC")
    oos_ok = True
    for tag, sub in (("DEV  2023-01 -> 2024-12", sig[sig["date"] < split]),
                     ("OOS  2025-01 -> 2026-08", sig[sig["date"] >= split])):
        if len(sub) < 100:
            print(f"  {tag}: only {len(sub)} signals - not evaluable")
            continue
        sub = sub.copy()
        sub["bin"] = bucketize(sub["rvol"], RVOL_BINS, labels)
        print(f"\n  {tag}   ({len(sub):,} signals)")
        print(f"    {'bin':<16}{'n':>7}{'mean fwd %':>13}{'t':>8}")
        ms = []
        for b in labels:
            s2 = sub[sub["bin"] == b]
            if len(s2) < 25:
                print(f"    {b:<16}{'-':>7}{'too few':>13}{'-':>8}")
                continue
            t2, m2, _, _ = tstat(s2["fwd"].to_numpy())
            ms.append(m2)
            print(f"    {b:<16}{len(s2):>7,}{m2*100:>13.3f}{t2:>8.2f}")
        mono = len(ms) >= 3 and monotone_decreasing(ms)
        print(f"    monotone decreasing: {'YES' if mono else 'NO'}")
        if len(ms) >= 2 and mono:
            a = sub[sub["bin"] == labels[0]]["fwd"].to_numpy()
            b_ = sub[sub["bin"] == labels[-1]]["fwd"].to_numpy()
            se = np.sqrt(a.var(ddof=1) / len(a) + b_.var(ddof=1) / len(b_))
            print(f"    spread {abs(a.mean()-b_.mean())*1e4:.0f} bps, "
                  f"{(a.mean()-b_.mean())/se:+.2f} standard errors")
        if tag.startswith("OOS") and not mono:
            oos_ok = False
    head("VERDICT")
    print(f"  Q2 {'PASS' if m_all < 0 else 'FAIL'} · Q3 {'PASS' if q3 else 'FAIL'}"
          f" · Q4 {'PASS' if q4 else 'FAIL'}")
    if q3 and q4:
        print("\n  THE SIGNAL IS GRADED. That is a real, unexploited axis: the same")
        print("  events, sized by how strong they are, without needing one more trade.")
        print("  Per Q6 this is NOT carried into a backtest this round - a position")
        print("  rule chosen on this ranking is a new selection degree of freedom and")
        print("  needs its own preregistration, written before any P&L is seen.")
    else:
        print("\n  THE SIGNAL IS ALL-OR-NOTHING. Within the signals it fires, strength")
        print("  carries no usable gradient, so weighting by it has nothing to weight")
        print("  on. **The WEIGHT axis is closed, like the COUNT axis before it.**")
        print("  Two axes down, and the remaining ones (universe, horizon) were closed")
        print("  in sections 15c-3 and 18.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
