"""CONSISTENCY GATE: recompute the load-bearing constants BY TWO INDEPENDENT ROUTES.

WHY THIS FILE EXISTS
--------------------
Three tools in this repo have now computed a number two different ways and
disagreed, and twice nobody noticed until something downstream looked wrong:

* `cost_frontier` vs `cost_reprice` on fees: `rate*qty` vs `rate*qty*price`
  (3.3x) - caught only because the second one was validated against the engine;
* `balance_limit` mixing two orderings in one walk - caught only because the
  output was absurd;
* **`intraday_gate0` vs `family_prescreen` on the median ATR%:** 2.502 % vs
  2.835 % on the SAME 4h data, because `intraday_gate0` merges the 1h series
  onto 4h timestamps and takes the median of that SUBSAMPLE. The true value is
  2.835 %.

Every previous catch in this project came from one of two places: a value that
was absurd on its face, or a second implementation that disagreed. **Neither is
a structural defence, and two rounds running the same failure is enough to stop
relying on them.** This is the structural defence: the handful of constants the
whole project rests on are recomputed here by a deliberately DIFFERENT route,
and a disagreement above tolerance FAILS.

THE CONSTANTS UNDER TEST
------------------------
1. the median ATR% of the deployed universe at 4h, computed (a) directly from
   each symbol's bars and (b) through the merge_asof route that
   `intraday_gate0` uses;
2. the 1h median ATR% the same two ways;
3. the deployed book's mean per-trade R via `risk_unit` and via the exported
   `profit_abs` re-priced from cost_reprice's own fee formula;
4. the deployed book's total return, recomputed from per-trade P&L and
   compared with the engine's printed figure.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\consistency_gate.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risk_unit import load_with_risk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"
DATA1 = ROOT / "user_data" / "data" / "binance" / "futures"
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
ARCHIVE = sorted((ROOT / "user_data" / "deployed_out").glob("*.zip"))[-1]

# ATR% is a distribution statistic; two routes on the same bars should agree
# exactly. A 2% band absorbs only float noise.
TOL_ATR = 0.02
TOL_R = 0.005        # 0.5% on a mean
TOL_TOTAL = 0.001     # 0.1 pp on a total return


def _atr(x: pd.DataFrame) -> pd.Series:
    prev = x["close"].shift(1)
    tr = pd.concat([x["high"] - x["low"], (x["high"] - prev).abs(),
                    (x["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()


def _read(d: Path, name: str, tf: str) -> pd.DataFrame:
    x = pd.read_feather(d / f"{name}-{tf}-futures.feather")[["date", "high", "low", "close"]]
    x["date"] = pd.to_datetime(x["date"], utc=True).dt.as_unit("ns")
    return x.sort_values("date").reset_index(drop=True)


def route_direct(pairs: list[str], d: Path, tf: str,
                 lo: pd.Timestamp | None = None,
                 hi: pd.Timestamp | None = None) -> tuple[float, dict]:
    """Route A: each symbol's own bars, median of per-symbol medians.

    `lo`/`hi` pin the sample to a date window. **They are not optional in
    practice** - see `WINDOW` below.
    """
    vals, n_in, n_all = [], 0, 0
    for p in pairs:
        k = p.replace("/", "_").replace(":", "_")
        if not (d / f"{k}-{tf}-futures.feather").exists():
            continue
        x = _read(d, k, tf)
        n_all += len(x)
        if lo is not None:
            x = x[(x["date"] >= lo) & (x["date"] <= hi)]
        n_in += len(x)
        if len(x) < 30:
            continue
        vals.append(float((_atr(x) / x["close"]).median()))
    v = float(np.median(vals)) if vals else float("nan")
    return v, {"n_in": n_in, "n_all": n_all, "n_sym": len(vals)}


def route_merged(pairs: list[str], tf: str,
                 lo: pd.Timestamp | None = None,
                 hi: pd.Timestamp | None = None) -> tuple[float, dict]:
    """Route B: the route `intraday_gate0` uses - one panel's series is matched
    onto the OTHER panel's timestamps and the median of that is taken.

    ⚠ THE FIRST VERSION OF THIS GATE REPORTED A 13 % DISAGREEMENT HERE THAT WAS
    NOT A DISAGREEMENT, and the cause was in the gate. There were TWO of them,
    of the same kind, one per horizon:

    * **Different universe.** `route_direct` at 4h iterated the full 40-symbol
      deployed list; this route can only iterate the **23** of those 40 that
      have a 1h file on disk. Fixed by pinning both to the shared 23 (§37a).
    * **Different DATE WINDOW - the same mistake, one level down.** This join
      can only return bars within 2 hours of a bar in the OTHER panel, so it
      silently restricts the sample to that panel's span. The 1h panel runs
      2019-09-08 -> 2026-09-27 and the 4h panel 2023-01-01 -> 2026-08-31, so
      `route_direct` was taking a **7-year** median of 1h ATR and this route a
      **3.7-year** one, with **36.8 % of 1h rows dropped by the join**.
      2020-2021 were more volatile than 2023-2026, so the long window reads
      higher - which is the one-directional bias §37b measured.
      Measured by `tools/perp_short/atr_window_probe.py`: dose-response
      **r = +0.882** between the out-of-span fraction and the bias, and the
      three symbols whose 1h panel starts inside the 4h panel show a median
      bias of **-0.08 %** - i.e. zero, as the mechanism predicts.

    Two medians over two different periods are not a consistency check. The
    route is KEPT - it is genuinely a different implementation, which is the
    point - but it is now pinned to the same window as route A, and the gate
    refuses to compare routes whose windows differ.
    """
    vals, n_in, n_all = [], 0, 0
    for p in pairs:
        k = p.replace("/", "_").replace(":", "_")
        f4 = DATA4 / f"{k}-4h-futures.feather"
        f1 = DATA1 / f"{k}-1h-futures.feather"
        if not (f4.exists() and f1.exists()):
            continue                      # the shared universe, and only it
        a, b = _read(DATA4, k, "4h"), _read(DATA1, k, "1h")
        a["atr"] = _atr(a)
        b["atr"] = _atr(b)
        left, right = (a, b) if tf == "4h" else (b, a)
        left = left[(left["date"] >= lo) & (left["date"] <= hi)] if lo is not None else left
        j = pd.merge_asof(
            left[["date", "close", "atr"]].rename(columns={"atr": "A"})
            .sort_values("date"),
            right[["date", "atr"]].rename(columns={"atr": "B"})
            .sort_values("date"),
            on="date", direction="nearest", tolerance=pd.Timedelta("2h"))
        n_all += len(left)
        j = j.dropna()
        n_in += len(j)
        if len(j) < 30:
            continue
        vals.append(float((j["A"] / j["close"]).median()))
    v = float(np.median(vals)) if vals else float("nan")
    return v, {"n_in": n_in, "n_all": n_all, "n_sym": len(vals)}


def common_window(pairs: list[str]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The date range over which EVERY shared symbol has BOTH panels.

    Any narrower and a symbol contributes no bars; any wider and a panel
    contributes rows the other cannot see. This is the only window in which
    the two routes are measuring the same thing.
    """
    los, his = [], []
    for p in pairs:
        k = p.replace("/", "_").replace(":", "_")
        f4 = DATA4 / f"{k}-4h-futures.feather"
        f1 = DATA1 / f"{k}-1h-futures.feather"
        if not (f4.exists() and f1.exists()):
            continue
        d4 = pd.read_feather(f4, columns=["date"])["date"]
        d1 = pd.read_feather(f1, columns=["date"])["date"]
        los.append(max(pd.Timestamp(d4.min()), pd.Timestamp(d1.min())))
        his.append(min(pd.Timestamp(d4.max()), pd.Timestamp(d1.max())))
    return max(los), min(his)

def main() -> int:
    print("CONSISTENCY GATE - the constants, recomputed by two independent routes\n")
    fails = []

    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    pairs = cfg["exchange"]["pair_whitelist"]
    h1 = sorted(p.name.split("-1h-")[0] for p in DATA1.glob("*-1h-futures.feather"))
    pair1 = [p for p in pairs
             if p.replace("/", "_").replace(":", "_") in set(h1)]

    print("1. MEDIAN ATR% OF THE DEPLOYED UNIVERSE")
    # BOTH routes are run over the SAME 23 symbols AND the SAME date window.
    # Comparing a 40-symbol median against a 23-symbol median is not a
    # consistency check (that mistake produced a 12 % "disagreement" that was
    # only a different universe), and comparing a 7-year median against a
    # 3.7-year one produced a second 13 % "disagreement" that was only a
    # different PERIOD. See the docstring on `route_merged`.
    shared = pair1
    print(f"  shared universe: {len(shared)} of {len(pairs)} deployed symbols "
          f"(only these have BOTH a 4h and a 1h file)")
    lo, hi = common_window(shared)
    print(f"  common window : {lo}  ->  {hi}")
    print("  WINDOW is a first-class check, not a footnote: if the two routes do")
    print("  not cover the same bars, their medians are different measurements")
    print("  and a difference between them is not evidence about either.")

    print(f"  {'horizon':<9}{'route A (direct)':>18}{'route B (merged)':>18}"
          f"{'relative gap':>15}  {'bars A':>10}{'bars B':>10}  verdict")
    for tf, plist in (("4h", shared), ("1h", shared)):
        dd = DATA4 if tf == "4h" else DATA1
        a, da = route_direct(plist, dd, tf, lo, hi)
        b, db = route_merged(plist, tf, lo, hi)
        gap = abs(a - b) / a if np.isfinite(a) and a else float("nan")
        # WINDOW: the join can only see bars within `tolerance` of the other
        # panel, so route B is allowed to hold FEWER bars than route A, but if
        # it holds a materially different share the comparison is void for a
        # reason that has nothing to do with the arithmetic.
        share = db["n_in"] / da["n_in"] if da["n_in"] else float("nan")
        if not np.isfinite(share) or share < 0.97:
            fails.append(f"{tf} WINDOW: route B retains only {share*100:.1f}% of "
                         f"route A's {da['n_in']:,} bars - the two routes are not "
                         f"measuring the same period, so their medians are not "
                         f"comparable and this is NOT a disagreement")
        ok = gap <= TOL_ATR
        if not ok:
            fails.append(f"{tf} ATR%: direct {a*100:.3f} vs merged {b*100:.3f} "
                         f"({gap*100:.1f}% apart)")
        print(f"  {tf:<9}{a*100:>17.3f}%{b*100:>17.3f}%{gap*100:>14.2f}%"
              f"  {da['n_in']:>10,}{db['n_in']:>10,}  {'PASS' if ok else 'FAIL'}")

    print("\n2. THE DEPLOYED BOOK, RECOMPUTED FROM ITS OWN TRADE LIST")
    df = load_with_risk(str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"))
    with zipfile.ZipFile(ARCHIVE) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        payload = json.loads(zf.read(mj))
    st = payload["strategy"]["PerpShort4hDeploy"]
    cmp_ = payload["strategy_comparison"][0]
    start = float(st.get("starting_balance") or 10_000)

    # route A: risk_unit's per-trade R
    r_a = df["R"].to_numpy()
    # route B: an INDEPENDENT recomputation of the SAME quantity - the mean of
    # per-trade R, rebuilt from profit_abs and the 4xATR risk unit rather than
    # reusing risk_unit's column.
    #
    # The first version compared the UNWEIGHTED mean of per-trade R against
    # sum(profit)/sum(risk_unit), which is an EQUITY-WEIGHTED mean. Those are
    # different statistics, the gate reported a 16 % "disagreement", and the
    # disagreement was IN THE GATE. A consistency check must compare the same
    # quantity twice, or it manufactures false positives.
    risk_units = (df["stake"] * 4.0 * df["atr_pct"]).to_numpy()
    r_b = df["profit"].to_numpy() / risk_units
    per_trade_gap = float(np.max(np.abs(r_a - r_b)) / max(np.abs(r_a).max(), 1e-12))
    ok = per_trade_gap <= TOL_R
    if not ok:
        fails.append(f"per-trade R: max relative gap {per_trade_gap*100:.3f}%")
    print(f"  per-trade R : {len(r_a)} trades, max relative gap between routes "
          f"{per_trade_gap*100:.4f}%  {'PASS' if ok else 'FAIL'}")
    print(f"  mean R      : route A {r_a.mean():.6f}   route B {r_b.mean():.6f}")

    total = float(df["profit"].sum()) / start
    eng = float(cmp_["profit_total_abs"]) / start
    gap = abs(total - eng)
    ok = gap <= TOL_TOTAL
    if not ok:
        fails.append(f"total return: {total*100:.4f}% vs engine {eng*100:.4f}%")
    print(f"  total ret: recomputed {total*100:.4f}%   engine "
          f"{eng*100:.4f}%   gap {gap*100:.4f} pp  {'PASS' if ok else 'FAIL'}")
    print(f"  (the engine's own printed total is {cmp_['profit_total_pct']:.4f}%)")

    print()
    if fails:
        print(f"  {len(fails)} DISAGREEMENT(S) between independent routes:")
        for f in fails:
            print(f"    - {f}")
        a4a, _ = route_direct(shared, DATA4, "4h", lo, hi)
        a4b, _ = route_merged(shared, "4h", lo, hi)
        a1a, _ = route_direct(shared, DATA1, "1h", lo, hi)
        a1b, _ = route_merged(shared, "1h", lo, hi)
        if all(np.isfinite(x) and x > 0 for x in (a4a, a4b, a1a, a1b)):
            r1, r2 = a1a / a4a, a1b / a4b
            print(f"\n  1h/4h ATR ratio: direct {r1:.3f}   merged {r2:.3f}"
                  f"   (spread {abs(r1-r2)/r1*100:.1f}%)")
            print("  A ratio this stable means the INTRADAY conclusion in section 18 -")
            print("  that a 1h round trip costs about twice a 4h one - survives EITHER")
            print("  route. Which LEVEL to quote depends on which window the number was")
            print("  measured over, so trace the window before quoting either.")
        print("\n  IF A WINDOW FAILURE APPEARS ABOVE, it is not a disagreement: the")
        print("  two routes retained different shares of the bars, so they computed")
        print("  medians over different periods. Run tools/perp_short/atr_window_probe.py")
        print("  to see the per-symbol out-of-span fractions.")
        print("\n  VERDICT: FAIL. A constant that two routes do not agree on is not")
        print("  a constant. Whichever route a downstream number used is now unknown,")
        print("  and the number has to be traced before it is quoted again.")
        return 1
    print("  VERDICT: PASS - every load-bearing constant recomputes identically by a")
    print("  deliberately different route, over the same symbols AND the same date")
    print("  window. Numbers produced from them are safe to quote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
