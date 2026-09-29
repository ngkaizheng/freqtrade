"""ATR WINDOW PROBE: is the consistency gate's 1h bias a DATE-WINDOW difference?

THE QUESTION
------------
`consistency_gate.py` reports that the median 1h ATR% computed DIRECTLY
(each symbol's own bars) disagrees with the same quantity computed through the
gate's `merge_asof` route by ~13%, one-directionally, on 20 of 23 symbols, with
ZERO rows dropped. Section 37b recorded that as unresolved.

Three candidate causes were already eliminated: a different universe (both
routes now use the same 23 symbols) and dropped rows (1,149,946 of 1,149,946
retained). This probe tests the FOURTH, which section 37b did not:

    **THE TWO ROUTES MAY COVER DIFFERENT DATE WINDOWS.**

The 1h panel is reported to run 2019-09-08 -> 2026-09-27 while the 4h panel
runs 2023-01-01 -> 2026-08-31. `route_direct` reads EVERY 1h bar it has.
`route_merged` keeps only 1h bars that sit within 2 hours of a 4h bar
timestamp, so it can only see the 4h panel's span. If the 1h panel really does
extend years beyond the 4h panel, the two medians are over different periods,
and the direction of the bias is then a PREDICTION, not a guess: 2020 and 2021
were more volatile than 2023-2026, so the longer window's median should be the
HIGHER one - which is exactly the sign §37b measured (merged is lower on 20 of
23).

A hypothesis that predicts the sign of a previously unexplained asymmetry is
worth testing. This tool tests it and reports what it finds, including if the
answer is no.

WHAT IT IS AND IS NOT
---------------------
* It is a DIAGNOSTIC, not a replacement for `consistency_gate.py`. The gate
  stays the gate; this decides what the gate should compare.
* It is an INDEPENDENT implementation of the ATR statistic (its own code, no
  import from the gate), because the whole point of the surrounding work is
  that two implementations of the same arithmetic agreeing is the only reliable
  tell. The ATR DEFINITION is deliberately identical (Wilder's smoothing,
  `ewm(alpha=1/14, adjust=False, min_periods=14)`) because a different
  definition would make the comparison meaningless; the CODE PATH is separate.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\atr_window_probe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"
DATA1 = ROOT / "user_data" / "data" / "binance" / "futures"
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"


def atr_pct(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """True range / close, Wilder-smoothed. Written independently of the gate.

    Implemented on raw numpy arrays rather than a pandas frame so that it shares
    no code with `consistency_gate._atr`; the previous four rounds of this file's
    family all turned on a shared-code mistake surviving undetected.
    """
    n = close.size
    tr = np.empty(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    if n > 1:
        tr[1:] = np.maximum.reduce([
            high[1:] - low[1:],
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ])
    # Wilder's RMA == ewm(alpha=1/14, adjust=False)
    alpha = 1.0 / 14.0
    out = np.empty(n, dtype=np.float64)
    out[:14] = np.nan
    acc = np.nanmean(tr[1:15]) if n > 15 else tr[:14].mean()
    out[14] = acc
    for i in range(15, n):
        acc = acc + alpha * (tr[i] - acc)
        out[i] = acc
    return out / close


def load(d: Path, name: str, tf: str) -> pd.DataFrame:
    f = d / f"{name}-{tf}-futures.feather"
    x = pd.read_feather(f)[["date", "high", "low", "close"]]
    x["date"] = pd.to_datetime(x["date"], utc=True).dt.as_unit("ns")
    return x.sort_values("date").reset_index(drop=True)


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    pairs = cfg["exchange"]["pair_whitelist"]
    have1 = {p.name.split("-1h-")[0] for p in DATA1.glob("*-1h-futures.feather")}
    shared = [p for p in pairs if p.replace("/", "_").replace(":", "_") in have1]

    print("ATR WINDOW PROBE - direct-vs-merged, split by DATE WINDOW\n")
    print(f"shared universe: {len(shared)} of {len(pairs)} deployed symbols\n")

    rows = []
    for p in shared:
        k = p.replace("/", "_").replace(":", "_")
        a4 = load(DATA4, k, "4h")
        a1 = load(DATA1, k, "1h")
        pct1 = atr_pct(a1["high"].to_numpy(), a1["low"].to_numpy(), a1["close"].to_numpy())
        t0, t1 = a4["date"].iloc[0], a4["date"].iloc[-1]
        inside = (a1["date"] >= t0) & (a1["date"] <= t1)
        v_all = float(np.nanmedian(pct1))
        v_win = float(np.nanmedian(pct1[inside.to_numpy()])) if inside.any() else float("nan")
        rows.append({
            "pair": k, "n1h": int(len(a1)), "n_in": int(inside.sum()),
            "d1_lo": a1["date"].iloc[0], "d1_hi": a1["date"].iloc[-1],
            "d4_lo": t0, "d4_hi": t1,
            "all": v_all, "win": v_win,
        })

    df = pd.DataFrame(rows)
    m_all, m_win = float(df["all"].median()), float(df["win"].median())

    print(f"{'pair':<22}{'1h bars':>9}{'in 4h span':>12}{'1h first':>12}"
          f"{'1h last':>12}{'all-bars %':>12}{'in-span %':>11}{'gap':>8}")
    for r in rows:
        gap = (r["all"] - r["win"]) / r["win"] if r["win"] else float("nan")
        print(f"{r['pair']:<22}{r['n1h']:>9,}{r['n_in']:>12,}"
              f"{str(r['d1_lo'])[:10]:>12}{str(r['d1_hi'])[:10]:>12}"
              f"{r['all']*100:>11.3f}%{r['win']*100:>10.3f}%{gap*100:>7.2f}%")

    # --- The magnitude, not just the sign -----------------------------------
    # If the cause is the window, then the bias should grow with the FRACTION
    # of 1h bars the 4h panel cannot see, not merely be positive. A sign match
    # is a coincidence; a dose-response is a mechanism.
    df["out_frac"] = (df["n1h"] - df["n_in"]) / df["n1h"]
    df["gap"] = (df["all"] - df["win"]) / df["win"]
    r = float(np.corrcoef(df["out_frac"], df["gap"])[0, 1])
    print("\nDOSE-RESPONSE: bias vs the fraction of 1h bars the 4h panel cannot see")
    print(f"  Pearson r = {r:+.3f} over {len(df)} symbols")
    lo = df[df["out_frac"] < 0.05]
    hi = df[df["out_frac"] > 0.30]
    print(f"  symbols with <5 % of bars out of span  (n={len(lo):2d}): "
          f"median bias {lo['gap'].median()*100:+.2f} %")
    print(f"  symbols with >30 % of bars out of span (n={len(hi):2d}): "
          f"median bias {hi['gap'].median()*100:+.2f} %")

    # --- What the merge ACTUALLY retains -------------------------------------
    # Section 37b recorded "1,149,946 of 1,149,946 1h rows retained, 0
    # dropped". This measures the real number with the gate's own join.
    tot = kept = 0
    for p in shared:
        k = p.replace("/", "_").replace(":", "_")
        a4 = load(DATA4, k, "4h")
        a1 = load(DATA1, k, "1h")
        a4["atr"] = a4["high"] - a4["low"]           # placeholder, B is dropped
        j = pd.merge_asof(
            a1[["date", "close"]].sort_values("date"),
            a4[["date", "atr"]].sort_values("date"),
            on="date", direction="nearest", tolerance=pd.Timedelta("2h"))
        tot += len(a1)
        kept += int(j["atr"].notna().sum())
    print("\nWHAT THE MERGE ACTUALLY RETAINS")
    print(f"  1h rows in   : {tot:,}")
    print(f"  1h rows kept: {kept:,}   DROPPED {tot-kept:,} ({(tot-kept)/tot*100:.1f} %)")
    print("  -> the '0 dropped' figure in section 37b cannot be a count of 1h rows")
    print("     surviving this join. See the note in the module docstring.")

    print("\nAGGREGATE (median of the 23 per-symbol medians)")
    print(f"  direct over ALL 1h bars      : {m_all*100:.3f}%")
    print(f"  direct over the 4h SPAN only : {m_win*100:.3f}%")
    gap = abs(m_all - m_win) / m_all
    print(f"  difference                   : {gap*100:.2f}%")
    print(f"  1h panel first bar           : {df['d1_lo'].min()}")
    print(f"  4h panel first bar           : {df['d4_lo'].min()}")
    print(f"  symbols where the 1h panel extends BEFORE the 4h panel: "
          f"{int((df['d1_lo'] < df['d4_lo']).sum())} of {len(df)}")
    print(f"  symbols where the 1h panel extends AFTER  the 4h panel: "
          f"{int((df['d1_hi'] > df['d4_hi']).sum())} of {len(df)}")
    print(f"  1h bars falling OUTSIDE the 4h span: "
          f"{int((df['n1h'] - df['n_in']).sum()):,} of {int(df['n1h'].sum()):,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
